"""Authenticated loopback RPC for wallets and local operator tooling."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import secrets
import stat
from pathlib import Path
from typing import Optional

import redis
from aiohttp import web
from base58 import b58decode_check

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.exceptions import TransactionNotValid
from luracoin.transactions import Transaction

DEFAULT_RPC_HOST = "127.0.0.1"
DEFAULT_RPC_PORT = 18444
NETWORK_RPC_PORTS = {"mainnet": 8444, "testnet": 18444, "devnet": 28444}
MAX_RPC_BODY = 1_000_000
log = logging.getLogger(__name__)


def load_or_create_rpc_token(path: Optional[str] = None) -> str:
    """Load the node RPC bearer token, creating a mode-0600 file if needed."""

    Config.ensure_data_dirs()
    token_path = Path(path or (Path(Config.DATA_DIR) / "rpc.token"))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        token = _read_rpc_token(token_path)
    except FileNotFoundError:
        token = secrets.token_urlsafe(48)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(token_path, flags, 0o600)
        except FileExistsError:
            # Another process may have created the token between our read and
            # exclusive create. Re-read and validate that file instead of
            # replacing it.
            token = _read_rpc_token(token_path)
        else:
            try:
                payload = f"{token}\n".encode()
                written = 0
                while written < len(payload):
                    written += os.write(descriptor, payload[written:])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    if len(token) < 32:
        raise RuntimeError(f"RPC token in {token_path} is too short")
    try:
        token_path.chmod(0o600)
    except OSError:
        # Some filesystems do not expose POSIX modes. Authentication still
        # remains mandatory, but callers should protect the data directory.
        pass
    return token


def _read_rpc_token(token_path: Path) -> str:
    """Read a small, private token file without following symbolic links."""

    path_metadata = token_path.lstat()
    if stat.S_ISLNK(path_metadata.st_mode) or not stat.S_ISREG(
        path_metadata.st_mode
    ):
        raise RuntimeError(
            f"RPC token path is not a regular file: {token_path}"
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(token_path, flags)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to open RPC token securely: {token_path}"
        ) from exc

    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(
                f"RPC token path is not a regular file: {token_path}"
            )
        if (metadata.st_dev, metadata.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise RuntimeError(
                f"RPC token changed while opening: {token_path}"
            )
        if metadata.st_size > 4_096:
            raise RuntimeError(
                f"RPC token file is unexpectedly large: {token_path}"
            )
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise RuntimeError(
                f"RPC token is owned by another user: {token_path}"
            )
        if os.name == "posix" and stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(
                f"RPC token permissions must not allow group or other access: "
                f"{token_path}"
            )

        payload = bytearray()
        while len(payload) <= 4_096:
            chunk = os.read(descriptor, min(1_024, 4_097 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > 4_096:
            raise RuntimeError(
                f"RPC token file is unexpectedly large: {token_path}"
            )
    finally:
        os.close(descriptor)

    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"RPC token is not valid UTF-8: {token_path}"
        ) from exc
    token = text.rstrip("\r\n")
    if text not in {token, f"{token}\n", f"{token}\r\n"} or any(
        character.isspace() for character in token
    ):
        raise RuntimeError(
            f"RPC token contains invalid whitespace: {token_path}"
        )
    return token


def _valid_address(address: str) -> bool:
    if not isinstance(address, str) or len(address) != 34:
        return False
    try:
        payload = b58decode_check(address)
    except (ValueError, TypeError):
        return False
    return len(payload) == 21 and payload[0] == 0x30


class RpcServer:
    """Small, authenticated HTTP API bound to the local machine only."""

    def __init__(
        self,
        *,
        node=None,
        host: str = DEFAULT_RPC_HOST,
        port: Optional[int] = None,
        token: Optional[str] = None,
        token_path: Optional[str] = None,
    ) -> None:
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("RPC may only bind to a loopback address")
        self.node = node
        self.host = host
        self.port = NETWORK_RPC_PORTS[Config.NETWORK] if port is None else port
        self.token = token or load_or_create_rpc_token(token_path)
        if len(self.token) < 32:
            raise ValueError("RPC token must contain at least 32 characters")
        self._runner = None
        self._site = None

    @web.middleware
    async def _authenticate(self, request: web.Request, handler):
        if request.path == "/health":
            return await handler(request)
        authorization = request.headers.get("Authorization", "")
        supplied = authorization.removeprefix("Bearer ")
        if not authorization.startswith("Bearer ") or not hmac.compare_digest(
            supplied, self.token
        ):
            raise web.HTTPUnauthorized(
                text=json.dumps({"error": "unauthorized"}),
                content_type="application/json",
            )
        return await handler(request)

    def create_app(self) -> web.Application:
        app = web.Application(
            middlewares=[self._authenticate], client_max_size=MAX_RPC_BODY
        )
        app.router.add_get("/health", self._health)
        app.router.add_get("/v1/status", self._status)
        app.router.add_get("/v1/accounts/{address}", self._account)
        app.router.add_get(
            "/v1/accounts/{address}/transactions", self._account_transactions
        )
        app.router.add_get("/v1/blocks/{height}", self._block)
        app.router.add_post("/v1/transactions", self._submit_transaction)
        return app

    async def start(self) -> None:
        if self._runner is not None:
            return
        self._runner = web.AppRunner(self.create_app(), access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _health(self, _request: web.Request) -> web.Response:
        return web.json_response(
            {"ok": True, "network": Config.NETWORK, "api_version": 1}
        )

    async def _status(self, _request: web.Request) -> web.Response:
        chain = self.node.chain if self.node is not None else Chain()
        peers = []
        if self.node is not None:
            for peer in self.node.peers.values():
                peers.append(
                    {
                        "host": peer.host,
                        "port": peer.port,
                        "inbound": peer.inbound,
                        "height": (peer.version_info or {}).get("height"),
                        "last_seen": peer.last_seen,
                    }
                )
        initialized = chain.get_block_file_number(0) is not None
        best_peer_height = chain.tip if initialized else -1
        ready = initialized
        syncing = False
        if self.node is not None:
            best_peer_height = self.node.best_peer_height
            ready = self.node.ready
            syncing = self.node.syncing
        return web.json_response(
            {
                **Config.network_summary(),
                "api_version": 1,
                "initialized": initialized,
                "height": chain.tip if initialized else -1,
                "best_peer_height": best_peer_height,
                "peer_count": len(peers),
                "peers": peers,
                "syncing": bool(syncing),
                "ready": bool(ready),
            }
        )

    async def _account(self, request: web.Request) -> web.Response:
        address = request.match_info["address"]
        if not _valid_address(address):
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_address"}),
                content_type="application/json",
            )
        account = Chain().get_account(address) or {"balance": 0, "nonce": 0}
        mempool = _mempool_account_view(address, account)
        return web.json_response(
            {
                "network": Config.NETWORK,
                "address": address,
                # Monetary values cross the JSON boundary as decimal strings;
                # JavaScript numbers cannot exactly represent uint64 values.
                "balance": str(account["balance"]),
                "spendable_balance": str(mempool["balance"]),
                "nonce": account["nonce"],
                "next_nonce": mempool["next_nonce"],
                "pending_outgoing_count": len(mempool["transactions"]),
                "mempool_available": mempool["available"],
            }
        )

    async def _account_transactions(
        self, request: web.Request
    ) -> web.Response:
        address = request.match_info["address"]
        if not _valid_address(address):
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_address"}),
                content_type="application/json",
            )
        try:
            limit = min(max(int(request.query.get("limit", "50")), 1), 200)
        except ValueError as exc:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_limit"}),
                content_type="application/json",
            ) from exc
        cursor = request.query.get("cursor")
        chain_cursor = None if cursor == "latest" else cursor

        chain = Chain()
        initialized = chain.get_block_file_number(0) is not None
        account = chain.get_account(address) or {"balance": 0, "nonce": 0}
        mempool = _mempool_account_view(address, account)
        # Pending items are volatile and therefore only appear on the first
        # page. Repeating them on every confirmed-history page would make a
        # client loop or show duplicates while the mempool remains unchanged.
        transactions = []
        if cursor is None:
            transactions = list(reversed(mempool["transactions"]))[:limit]

        next_cursor = None
        if initialized or cursor is not None:
            confirmed_limit = limit - len(transactions)
            # If pending transactions fill the first page, return a sentinel
            # cursor which starts the next request at the newest indexed item.
            lookup_limit = max(1, confirmed_limit)
            try:
                references, indexed_cursor = (
                    chain.get_address_transaction_refs(
                        address,
                        limit=lookup_limit,
                        cursor=chain_cursor,
                    )
                )
            except ValueError as exc:
                raise web.HTTPBadRequest(
                    text=json.dumps({"error": "invalid_cursor"}),
                    content_type="application/json",
                ) from exc

            if confirmed_limit == 0:
                if references:
                    next_cursor = "latest"
            else:
                indexed_blocks = await asyncio.to_thread(
                    Block.get_many,
                    [reference["height"] for reference in references],
                )
                for reference in references:
                    block = indexed_blocks.get(reference["height"])
                    if block is None or reference["index"] >= len(block.txns):
                        log.warning(
                            "Ignoring stale address index entry at %s:%s",
                            reference["height"],
                            reference["index"],
                        )
                        continue
                    transaction = block.txns[reference["index"]]
                    if transaction.id != reference["transaction_id"]:
                        log.warning(
                            "Ignoring mismatched address index entry at %s:%s",
                            reference["height"],
                            reference["index"],
                        )
                        continue
                    item = _transaction_json(transaction)
                    item["block_height"] = reference["height"]
                    item["timestamp"] = block.timestamp
                    item["status"] = "confirmed"
                    transactions.append(item)
                next_cursor = indexed_cursor
        return web.json_response(
            {
                "network": Config.NETWORK,
                "address": address,
                "mempool_available": mempool["available"],
                "transactions": transactions,
                "next_cursor": next_cursor,
            }
        )

    async def _block(self, request: web.Request) -> web.Response:
        try:
            height = int(request.match_info["height"])
        except ValueError as exc:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_height"}),
                content_type="application/json",
            ) from exc
        if height < 0:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_height"}),
                content_type="application/json",
            )
        block = await asyncio.to_thread(Block.get, height)
        if block is None:
            raise web.HTTPNotFound(
                text=json.dumps({"error": "block_not_found"}),
                content_type="application/json",
            )
        payload = block.json()
        payload["network"] = Config.NETWORK
        payload["txns"] = [_transaction_json(tx) for tx in block.txns]
        return web.json_response(payload)

    async def _submit_transaction(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            raw_hex = body["raw"]
            raw = bytes.fromhex(raw_hex)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_transaction_encoding"}),
                content_type="application/json",
            ) from exc
        if len(raw) != Config.TRANSACTION_LENGTH:
            raise web.HTTPBadRequest(
                text=json.dumps(
                    {
                        "error": "invalid_transaction_length",
                        "expected": Config.TRANSACTION_LENGTH,
                        "actual": len(raw),
                    }
                ),
                content_type="application/json",
            )

        if self.node is not None and not self.node.ready:
            raise web.HTTPServiceUnavailable(
                text=json.dumps({"error": "node_not_ready"}),
                content_type="application/json",
            )

        transaction = Transaction()
        try:
            transaction.deserialize(raw)
            accepted = transaction.to_transaction_pool()
        except redis.exceptions.RedisError as exc:
            raise web.HTTPServiceUnavailable(
                text=json.dumps({"error": "mempool_unavailable"}),
                content_type="application/json",
            ) from exc
        except Exception as exc:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_transaction"}),
                content_type="application/json",
            ) from exc
        if not accepted:
            raise web.HTTPUnprocessableEntity(
                text=json.dumps({"error": "transaction_rejected"}),
                content_type="application/json",
            )

        relay_count = 0
        if self.node is not None:
            try:
                relay_count = await self.node.broadcast_tx(transaction)
            except Exception:
                # Acceptance into the local mempool already happened. Do not
                # report a false rejection that would encourage re-signing.
                # The response exposes zero successful relays while the local
                # mempool (and any local miner) retains the transaction.
                relay_count = 0
                log.exception("Transaction accepted but initial relay failed")
        if not isinstance(relay_count, int) or relay_count < 0:
            relay_count = 0
        return web.json_response(
            {
                "network": Config.NETWORK,
                "accepted": True,
                "broadcast": relay_count > 0,
                "relay_count": relay_count,
                "transaction": {
                    **_transaction_json(transaction),
                    "status": "pending",
                    "block_height": None,
                    "timestamp": None,
                },
            },
            status=202,
        )


def _transaction_json(transaction: Transaction) -> dict:
    """Return an RPC-safe transaction representation without lossy numbers."""

    payload = transaction.json()
    payload["fee"] = str(transaction.fee)
    payload["value"] = str(transaction.value)
    return payload


def _mempool_account_view(address: str, account: dict) -> dict:
    """Return contiguous pending spends and their simulated account state."""

    balance = int(account["balance"])
    nonce = int(account["nonce"])
    transactions = []
    client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )
    try:
        for pending_nonce in range(
            nonce + 1, nonce + Config.MAX_TX_PER_BLOCK + 1
        ):
            nonce_key = Transaction.mempool_nonce_key_for(
                Config.CHAIN_ID, address, pending_nonce
            )
            transaction_id = client.get(nonce_key)
            if not transaction_id:
                break
            raw = client.get(transaction_id)
            if not raw:
                break
            transaction = Transaction().deserialize(raw)
            if (
                transaction.from_address != address
                or transaction.nonce != pending_nonce
                or transaction.value + transaction.fee > balance
            ):
                break
            balance -= transaction.value + transaction.fee
            if transaction.to_address == address:
                balance += transaction.value
            nonce = pending_nonce
            item = _transaction_json(transaction)
            item.update(
                {
                    "status": "pending",
                    "block_height": None,
                    "timestamp": None,
                }
            )
            transactions.append(item)
    except (
        redis.exceptions.RedisError,
        TransactionNotValid,
        UnicodeDecodeError,
    ):
        return {
            "available": False,
            "balance": int(account["balance"]),
            "next_nonce": int(account["nonce"]) + 1,
            "transactions": [],
        }
    return {
        "available": True,
        "balance": balance,
        "next_nonce": nonce + 1,
        "transactions": transactions,
    }
