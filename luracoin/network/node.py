"""Main P2P node: server, peer lifecycle, and message dispatch."""

import asyncio
import binascii
import contextlib
import ipaddress
import logging
import secrets
import time
from collections import deque

import redis

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.network.discovery import PeerDiscovery
from luracoin.network.peer import PeerConnection
from luracoin.network.protocol import (
    CMD_BLOCK,
    CMD_GETBLOCKS,
    CMD_GETDATA,
    CMD_GETPEERS,
    CMD_INV,
    CMD_PEERS,
    CMD_PING,
    CMD_PONG,
    CMD_TX,
    CMD_VERACK,
    CMD_VERSION,
    INV_BLOCK,
    INV_TX,
    PROTOCOL_VERSION,
    build_inv_payload,
    build_ping_payload,
    parse_getblocks_payload,
    parse_inv_payload,
    parse_ping_payload,
)
from luracoin.network.sync import BlockSync

log = logging.getLogger(__name__)


_MEMPOOL_EVICT_PENDING_SCRIPT = """
local claimed = redis.call('GET', KEYS[1])
local payload = redis.call('GET', KEYS[2])
local removed = 0
if claimed == ARGV[1] then
    removed = removed + redis.call('DEL', KEYS[1])
end
if payload == ARGV[2] then
    removed = removed + redis.call('DEL', KEYS[2])
end
return removed
"""


class ProtocolError(Exception):
    """The peer sent a message that is invalid in the current state."""


class Node:
    """A Luracoin P2P node with one reader/dispatcher per connection."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = None,
        seed_nodes: list = None,
        max_peers: int = None,
        ping_interval: int = None,
        max_inbound_peers: int = None,
    ):
        self.host = host
        self.port = Config.PORT if port is None else port
        self.chain = Chain()
        self.block_sync = BlockSync(self.chain, Block)
        self.max_peers = Config.MAX_PEERS if max_peers is None else max_peers
        self.max_inbound_peers = (
            Config.MAX_INBOUND_PEERS
            if max_inbound_peers is None
            else max_inbound_peers
        )
        self.ping_interval = (
            Config.PING_INTERVAL if ping_interval is None else ping_interval
        )
        seeds = Config.SEED_NODES if seed_nodes is None else seed_nodes
        self.discovery = PeerDiscovery(
            seed_nodes=seeds,
            max_peers=self.max_peers,
            local_port=self.port,
        )

        self.peers: dict = {}
        self.running = False
        self._server = None
        self._pending_inbound = 0
        self._pending_outbound: set = set()
        self._inbound_tasks: set = set()
        self._reader_tasks: dict = {}
        self._sync_tasks: dict = {}
        self._sync_queues: dict = {}
        self._sync_peer_cooldowns: dict = {}
        self._sync_peer_failures: dict = {}
        self._peer_addresses: dict = {}
        self._pong_waiters: dict = {}
        self._ping_task = None
        self._maintenance_task = None
        self._ping_cycle_lock = asyncio.Lock()

        # Keep the public set for compatibility while bounding all additions
        # performed by this node. Relay tracking is type-aware and separately
        # bounded, so a seen INV does not prevent forwarding accepted data.
        self.known_invs: set = set()
        self._known_inv_order = deque()
        self._relayed_invs: set = set()
        self._relayed_inv_order = deque()
        # Transactions accepted while there are no peers must not become
        # permanently stranded in the local Redis mempool.  Keep a bounded,
        # process-local relay backlog and replay it to peers as they become
        # usable. Confirmed transactions are removed when their block arrives
        # or is broadcast by this node.
        self._pending_tx_relays: dict[bytes, bytes] = {}
        self._pending_relay_cursors: dict = {}
        self.on_new_block = None
        self.on_sync_needed = None

    @property
    def connected_addresses(self) -> set:
        return set(self.peers.keys())

    @property
    def best_peer_height(self) -> int:
        """Highest chain height currently known from this node or its peers."""

        heights = [self.chain.tip]
        for peer in self.peers.values():
            info = getattr(peer, "version_info", None) or {}
            height = info.get("height")
            if (
                getattr(peer, "connected", False)
                and isinstance(height, int)
                and height >= 0
            ):
                heights.append(height)
        return max(heights)

    @property
    def syncing(self) -> bool:
        """Whether a sync task is active, including task-start/stop races."""

        return self.block_sync.syncing or any(
            not task.done() for task in self._sync_tasks.values()
        )

    @property
    def ready(self) -> bool:
        """Whether state is initialized and caught up with known peers."""

        initialized = self.chain.get_block_file_number(0) is not None
        return (
            initialized
            and not self.syncing
            and self.chain.tip >= self.best_peer_height
        )

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start accepting peers and launch the periodic keep-alive task."""
        if self.running:
            return
        self._server = await asyncio.start_server(
            self._handle_inbound, self.host, self.port
        )
        self.running = True

        # Port zero is useful for isolated nodes and real socket tests.
        sockets = self._server.sockets or []
        if sockets:
            self.port = sockets[0].getsockname()[1]
            self.discovery.local_port = self.port
        for listening_socket in sockets:
            self.discovery.add_local_address(listening_socket.getsockname()[0])

        self._ping_task = asyncio.create_task(
            self._ping_loop(), name=f"luracoin-ping-{self.port}"
        )
        self._maintenance_task = asyncio.create_task(
            self._peer_maintenance_loop(),
            name=f"luracoin-discovery-{self.port}",
        )
        log.info("Node listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        """Stop accepting work, cancel tasks, and close every socket."""
        self.running = False

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        current = asyncio.current_task()
        tasks = set(self._inbound_tasks)
        tasks.update(self._reader_tasks.values())
        tasks.update(self._sync_tasks.values())
        if self._ping_task is not None:
            tasks.add(self._ping_task)
        if self._maintenance_task is not None:
            tasks.add(self._maintenance_task)
        tasks.discard(current)
        for task in tasks:
            if not task.done():
                task.cancel()

        for future in list(self._pong_waiters.values()):
            if not future.done():
                future.cancel()
        self._pong_waiters.clear()

        unique_peers = []
        for peer in self.peers.values():
            if all(existing is not peer for existing in unique_peers):
                unique_peers.append(peer)
        for peer in unique_peers:
            await peer.disconnect()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.peers.clear()
        self._peer_addresses.clear()
        self._reader_tasks.clear()
        self._sync_tasks.clear()
        self._sync_queues.clear()
        self._sync_peer_cooldowns.clear()
        self._sync_peer_failures.clear()
        self._pending_relay_cursors.clear()
        self._inbound_tasks.clear()
        self._pending_outbound.clear()
        self._pending_inbound = 0
        self._ping_task = None
        self._maintenance_task = None
        self.block_sync.syncing = False

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    def _inbound_capacity_available(self) -> bool:
        inbound = sum(1 for peer in self.peers.values() if peer.inbound)
        return (
            inbound + self._pending_inbound < self.max_inbound_peers
            and len(self.peers)
            + self._pending_inbound
            + len(self._pending_outbound)
            < self.max_peers
        )

    async def _handle_inbound(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Authenticate and register one incoming TCP connection."""
        task = asyncio.current_task()
        if task is not None:
            self._inbound_tasks.add(task)
        peer = None
        registered = False

        if not self.running or not self._inbound_capacity_available():
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            if task is not None:
                self._inbound_tasks.discard(task)
            return

        self._pending_inbound += 1
        try:
            peername = writer.get_extra_info("peername")
            if not peername:
                return
            host, source_port = peername[0], peername[1]
            log.info("Inbound connection from %s:%s", host, source_port)
            peer = PeerConnection(
                reader, writer, host, source_port, inbound=True
            )
            ok = await peer.handshake(
                local_version=PROTOCOL_VERSION,
                local_height=self.chain.tip,
                local_port=self.port,
            )
            if not ok or not self._compatible_version(peer.version_info):
                return

            listening_port = peer.version_info["listening_port"]
            peer.port = listening_port
            registered = await self._activate_peer(
                peer, (host, listening_port)
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Inbound peer setup failed")
        finally:
            self._pending_inbound = max(0, self._pending_inbound - 1)
            if peer is None:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
            elif not registered:
                await peer.disconnect()
            if task is not None:
                self._inbound_tasks.discard(task)

    async def connect_to_peer(self, host: str, port: int) -> bool:
        """Initiate an outbound connection and hand it to the dispatcher."""
        addr = (host, port)
        if addr in self.peers or addr in self._pending_outbound:
            return False
        if self._sync_cooldown_active(addr):
            return False
        if self.discovery._is_self(host, port):
            return False
        if (
            len(self.peers)
            + len(self._pending_outbound)
            + self._pending_inbound
            >= self.max_peers
        ):
            return False

        self._pending_outbound.add(addr)
        peer = None
        registered = False
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
            peer = PeerConnection(reader, writer, host, port, inbound=False)
            ok = await peer.handshake(
                local_version=PROTOCOL_VERSION,
                local_height=self.chain.tip,
                local_port=self.port,
            )
            if not ok or not self._compatible_version(peer.version_info):
                return False
            registered = await self._activate_peer(peer, addr)
            return registered
        except (OSError, asyncio.TimeoutError, ConnectionError):
            self.discovery.remove_peer(host, port)
            return False
        finally:
            self._pending_outbound.discard(addr)
            if peer is not None and not registered:
                await peer.disconnect()

    def _compatible_version(self, version_info: dict) -> bool:
        """Reject old protocol versions, foreign chains, and unusable ports."""
        if not isinstance(version_info, dict):
            return False
        return (
            version_info.get("version") == PROTOCOL_VERSION
            and version_info.get("chain_id") == Config.CHAIN_ID
            and isinstance(version_info.get("height"), int)
            and 1 <= version_info.get("listening_port", 0) <= 0xFFFF
        )

    async def _activate_peer(self, peer: PeerConnection, addr: tuple) -> bool:
        """Register a handshaken peer and start its sole reader task."""
        if not self.running:
            return False
        self._learn_peer_socket_addresses(peer)
        remote_endpoint = self._peer_socket_endpoint(peer, "peername")
        listening_port = (peer.version_info or {}).get(
            "listening_port", addr[1]
        )
        if remote_endpoint is not None and self.discovery._is_self(
            remote_endpoint[0], listening_port
        ):
            self.discovery.remove_peer(*addr)
            return False
        if addr in self.peers or len(self.peers) >= self.max_peers:
            return False
        if self._sync_cooldown_active(addr):
            return False
        if self.discovery._is_self(*addr):
            return False

        peer._node_managed = True
        self.peers[addr] = peer
        self._peer_addresses[peer] = addr
        self._sync_queues[peer] = asyncio.Queue(
            maxsize=max(1, Config.SYNC_BATCH_SIZE * 2)
        )
        self.discovery.add_peer(*addr)
        reader_task = asyncio.create_task(
            self.listen_to_peer(peer),
            name=f"luracoin-peer-{addr[0]}:{addr[1]}",
        )
        self._reader_tasks[peer] = reader_task
        try:
            await self._post_handshake(peer)
        except (ConnectionError, OSError, ValueError):
            await self._remove_peer(peer)
            return False
        return True

    @staticmethod
    def _peer_socket_endpoint(peer: PeerConnection, name: str):
        writer = getattr(peer, "writer", None)
        get_extra_info = getattr(writer, "get_extra_info", None)
        if not callable(get_extra_info):
            return None
        try:
            endpoint = get_extra_info(name)
        except (OSError, TypeError, ValueError):
            return None
        if (
            not isinstance(endpoint, tuple)
            or len(endpoint) < 2
            or not isinstance(endpoint[0], str)
        ):
            return None
        return endpoint

    def _learn_peer_socket_addresses(self, peer: PeerConnection) -> None:
        local_endpoint = self._peer_socket_endpoint(peer, "sockname")
        if local_endpoint is not None:
            self.discovery.add_local_address(local_endpoint[0])

    async def _post_handshake(self, peer: PeerConnection) -> None:
        """Discover peers, schedule sync, and replay pending transactions."""
        await peer.send(CMD_GETPEERS)
        if self.block_sync.needs_sync(peer.version_info["height"]):
            scheduled = self._schedule_best_peer_sync()
            if scheduled and self.on_sync_needed:
                try:
                    self.on_sync_needed()
                except Exception:
                    log.exception("Sync-needed callback failed")
        elif self.ready:
            _sent, healthy = await self._relay_pending_to_peer(peer)
            if not healthy:
                raise ConnectionError("Pending transaction replay failed")

    def _address_for_peer(self, peer: PeerConnection) -> tuple:
        return self._peer_addresses.get(peer, (peer.host, peer.port))

    @staticmethod
    def _sync_peer_key(addr: tuple) -> str:
        """Normalize an address to a stable host/IP cooldown identity."""

        host = addr[0] if isinstance(addr, tuple) else addr
        host = str(host).strip().lower()
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            return ipaddress.ip_address(host).compressed.lower()
        except ValueError:
            return host

    def _sync_cooldown_active(self, addr: tuple, *, now: float = None) -> bool:
        """Check whether an address is cooling down after a sync failure."""

        key = self._sync_peer_key(addr)
        deadline = self._sync_peer_cooldowns.get(key)
        if deadline is None:
            return False
        current = time.monotonic() if now is None else now
        if current >= deadline:
            self._sync_peer_cooldowns.pop(key, None)
            return False
        return True

    def _record_sync_failure(self, addr: tuple, *, now: float = None) -> float:
        """Apply an exponential, process-local cooldown to one peer address."""

        key = self._sync_peer_key(addr)
        previous_failures = self._sync_peer_failures.pop(key, 0)
        failures = min(previous_failures + 1, 32)
        self._sync_peer_failures[key] = failures
        base = max(0.0, float(Config.SYNC_PEER_COOLDOWN_BASE))
        maximum = max(base, float(Config.SYNC_PEER_COOLDOWN_MAX))
        delay = min(maximum, base * (2 ** (failures - 1)))
        current = time.monotonic() if now is None else now
        self._sync_peer_cooldowns.pop(key, None)
        self._sync_peer_cooldowns[key] = current + delay
        limit = max(1, int(Config.SYNC_PEER_COOLDOWN_LIMIT))
        while len(self._sync_peer_failures) > limit:
            oldest = next(iter(self._sync_peer_failures))
            self._sync_peer_failures.pop(oldest, None)
            self._sync_peer_cooldowns.pop(oldest, None)
        return delay

    def _clear_sync_failure(self, addr: tuple) -> None:
        key = self._sync_peer_key(addr)
        self._sync_peer_cooldowns.pop(key, None)
        self._sync_peer_failures.pop(key, None)

    def _schedule_sync(self, peer: PeerConnection) -> bool:
        # Chain application is sequential, so use a single active sync peer.
        if any(not task.done() for task in self._sync_tasks.values()):
            return False
        if (
            not self.running
            or not getattr(peer, "connected", False)
            or peer not in self._sync_queues
            or self._sync_cooldown_active(self._address_for_peer(peer))
            or not self.block_sync.needs_sync(peer.version_info["height"])
        ):
            return False
        task = asyncio.create_task(
            self._sync_from_peer(peer),
            name=f"luracoin-sync-{peer.host}:{peer.port}",
        )
        self._sync_tasks[peer] = task
        return True

    def _schedule_best_peer_sync(self) -> bool:
        """Schedule the most advanced connected peer when no sync is active."""

        if not self.running or any(
            not task.done() for task in self._sync_tasks.values()
        ):
            return False
        candidates = [
            peer
            for peer in self.peers.values()
            if getattr(peer, "connected", False)
            and peer in self._sync_queues
            and not self._sync_cooldown_active(self._address_for_peer(peer))
            and isinstance((peer.version_info or {}).get("height"), int)
            and self.block_sync.needs_sync(peer.version_info["height"])
        ]
        if not candidates:
            return False
        peer = max(candidates, key=lambda item: item.version_info["height"])
        return self._schedule_sync(peer)

    async def connect_to_seeds(self) -> None:
        """Connect to known addresses until the peer limit is reached."""
        to_connect = self.discovery.get_peers_to_connect(
            self.connected_addresses
        )
        for host, port in to_connect:
            if len(self.peers) + len(self._pending_outbound) >= self.max_peers:
                break
            if self._sync_cooldown_active((host, port)):
                continue
            await self.connect_to_peer(host, port)

    async def _peer_maintenance_loop(self) -> None:
        """Continuously connect to seeds and newly discovered addresses."""
        try:
            while self.running:
                await self.connect_to_seeds()
                # A peer may have been behind when it connected and rejected a
                # transaction before completing its own sync. Replaying this
                # bounded backlog makes relay eventually reliable without
                # treating a socket write as permanent delivery.
                if self.ready and self._pending_tx_relays:
                    await self._relay_pending_transactions()
                await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            raise

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def handle_message(
        self, peer: PeerConnection, command: bytes, payload: bytes
    ) -> None:
        """Dispatch a fully framed and structurally validated message."""
        if command == CMD_GETPEERS:
            response = self.discovery.build_peers_response()
            await peer.send(CMD_PEERS, response)
        elif command == CMD_PEERS:
            self._learn_peer_socket_addresses(peer)
            self.discovery.handle_peers_message(payload)
        elif command == CMD_GETBLOCKS:
            await self._handle_getblocks(peer, payload)
        elif command == CMD_BLOCK:
            await self._handle_received_block(peer, payload)
        elif command == CMD_TX:
            await self._handle_received_tx(peer, payload)
        elif command == CMD_INV:
            await self._handle_inv(peer, payload)
        elif command == CMD_GETDATA:
            await self._handle_getdata(peer, payload)
        elif command == CMD_PING:
            ping_data = parse_ping_payload(payload)
            await peer.send(CMD_PONG, build_ping_payload(ping_data["nonce"]))
        elif command == CMD_PONG:
            self._handle_pong(peer, payload)
        elif command in (CMD_VERSION, CMD_VERACK):
            raise ProtocolError("Handshake command received after handshake")
        else:
            raise ProtocolError("Unsupported P2P command")

    async def _handle_getblocks(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        data = parse_getblocks_payload(payload)
        start = data["start_height"]
        count = min(data["count"], Config.SYNC_BATCH_SIZE)
        for height in range(start, start + count):
            block = Block.get(height)
            if block is None:
                break
            await peer.send(CMD_BLOCK, block.serialize())

    def _handle_block(self, payload: bytes) -> bool:
        """Apply a block; retained as a synchronous compatibility hook."""
        accepted = self.block_sync.handle_block(payload)
        if accepted and self.on_new_block:
            try:
                self.on_new_block()
            except Exception:
                log.exception("New-block callback failed")
        return accepted

    async def _handle_received_block(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        block = None
        redis_evictions = []
        try:
            block = Block()
            block.deserialize(payload)
            # Block.save() removes the sender/nonce reservation, including
            # when it belongs to a different pending transaction. Capture the
            # exact candidate first so its otherwise orphaned payload can be
            # removed only after the block has been accepted.
            redis_evictions = self._snapshot_competing_transactions(block)
        except Exception:
            # The normal block handler owns rejection of malformed payloads.
            pass

        accepted = self._handle_block(payload)
        queue = self._sync_queues.get(peer)
        sync_task = self._sync_tasks.get(peer)
        if (
            queue is not None
            and sync_task is not None
            and not sync_task.done()
        ):
            try:
                queue.put_nowait(accepted)
            except asyncio.QueueFull:
                raise ProtocolError("Peer exceeded the active sync window")

        if not accepted:
            return
        if block is None:
            block = Block()
            block.deserialize(payload)
        peer.version_info["height"] = max(
            peer.version_info.get("height", 0), block.height
        )
        self._forget_confirmed_transactions(block, redis_evictions)
        hash_bytes = binascii.unhexlify(block.id)
        self._remember_inventory(hash_bytes)
        await self._relay_inventory(INV_BLOCK, hash_bytes, exclude=peer)

    def _handle_tx(self, payload: bytes) -> bool:
        try:
            tx = Transaction()
            tx.deserialize(payload)
            return tx.to_transaction_pool()
        except Exception:
            return False

    async def _handle_received_tx(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        if not self._handle_tx(payload):
            return
        tx = Transaction()
        tx.deserialize(payload)
        hash_bytes = binascii.unhexlify(tx.id)
        self._queue_pending_transaction(payload, hash_bytes)
        self._remember_inventory(hash_bytes)
        await self._relay_transaction(payload, hash_bytes, exclude=peer)

    async def _handle_inv(self, peer: PeerConnection, payload: bytes) -> None:
        inv_data = parse_inv_payload(payload)
        inv_hash = inv_data["hash"]
        if inv_hash in self.known_invs:
            return
        self._remember_inventory(inv_hash)
        await peer.send(
            CMD_GETDATA,
            build_inv_payload(inv_data["type"], inv_hash),
        )

    async def _handle_getdata(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        inv_data = parse_inv_payload(payload)
        if inv_data["type"] == INV_BLOCK:
            block_id_hex = inv_data["hash"].hex()
            height = self.chain.get_block_height(block_id_hex)
            block = Block.get(height) if height is not None else None
            if block is not None and block.id == block_id_hex:
                await peer.send(CMD_BLOCK, block.serialize())
        elif inv_data["type"] == INV_TX:
            try:
                client = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=Config.REDIS_DB,
                )
                tx_payload = client.get(inv_data["hash"].hex())
                if tx_payload:
                    await peer.send(CMD_TX, tx_payload)
            except Exception:
                log.debug(
                    "Unable to serve transaction inventory", exc_info=True
                )

    def _handle_pong(self, peer: PeerConnection, payload: bytes) -> None:
        nonce = parse_ping_payload(payload)["nonce"]
        future = self._pong_waiters.get((id(peer), nonce))
        if future is not None and not future.done():
            future.set_result(True)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def _sync_from_peer(self, peer: PeerConnection) -> None:
        """Download blocks while the reader handles all interleaving."""
        queue = self._sync_queues.get(peer)
        if queue is None:
            return
        failed = False
        cancelled = False
        addr = self._address_for_peer(peer)
        self.block_sync.syncing = True
        try:
            while (
                self.running
                and peer.connected
                and self.block_sync.needs_sync(peer.version_info["height"])
            ):
                while not queue.empty():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                getblocks_payload = self.block_sync.build_getblocks_request()
                data = parse_getblocks_payload(getblocks_payload)
                expected_count = min(
                    data["count"],
                    peer.version_info["height"] - self.chain.tip,
                )
                if expected_count <= 0:
                    break
                await peer.send(CMD_GETBLOCKS, getblocks_payload)
                blocks_received = 0
                for _ in range(expected_count):
                    try:
                        accepted = await asyncio.wait_for(
                            queue.get(), timeout=30.0
                        )
                    except asyncio.TimeoutError:
                        failed = True
                        break
                    if not accepted:
                        failed = True
                        break
                    blocks_received += 1
                if failed:
                    break
                if blocks_received == 0:
                    failed = True
                    break
        except asyncio.CancelledError:
            if self.running:
                try:
                    failed = self.block_sync.needs_sync(
                        peer.version_info["height"]
                    )
                except Exception:
                    failed = True
            cancelled = not failed
            raise
        except Exception:
            failed = True
            log.info(
                "Sync failed for peer %s:%s",
                peer.host,
                peer.port,
                exc_info=True,
            )
        finally:
            self.block_sync.syncing = False
            current = asyncio.current_task()
            if self._sync_tasks.get(peer) is current:
                self._sync_tasks.pop(peer, None)
            if self.running and not cancelled:
                if failed:
                    delay = self._record_sync_failure(addr)
                    log.info(
                        "Cooling peer %s:%s for %.1fs after failed sync",
                        peer.host,
                        peer.port,
                        delay,
                    )
                    await self._remove_peer(peer)
                else:
                    self._clear_sync_failure(addr)
                scheduled = self._schedule_best_peer_sync()
                if not scheduled and self.ready:
                    await self._relay_pending_transactions()

    # ------------------------------------------------------------------
    # Inventory and broadcasting
    # ------------------------------------------------------------------

    def _remember_inventory(self, hash_bytes: bytes) -> bool:
        if not isinstance(hash_bytes, bytes) or len(hash_bytes) != 32:
            raise ValueError("Inventory hash must contain exactly 32 bytes")
        if hash_bytes in self.known_invs:
            return False
        self.known_invs.add(hash_bytes)
        self._known_inv_order.append(hash_bytes)
        while len(self.known_invs) > Config.KNOWN_INV_LIMIT:
            if self._known_inv_order:
                oldest = self._known_inv_order.popleft()
            else:
                oldest = next(iter(self.known_invs))
            self.known_invs.discard(oldest)
        return True

    def _remember_relay(self, inv_type: int, hash_bytes: bytes) -> bool:
        if inv_type not in (INV_BLOCK, INV_TX):
            raise ValueError("Unsupported inventory type")
        if not isinstance(hash_bytes, bytes) or len(hash_bytes) != 32:
            raise ValueError("Inventory hash must contain exactly 32 bytes")
        key = (inv_type, hash_bytes)
        if key in self._relayed_invs:
            return False
        self._relayed_invs.add(key)
        self._relayed_inv_order.append(key)
        while len(self._relayed_invs) > Config.KNOWN_INV_LIMIT:
            oldest = self._relayed_inv_order.popleft()
            self._relayed_invs.discard(oldest)
        return True

    def _queue_pending_transaction(
        self, payload: bytes, hash_bytes: bytes
    ) -> None:
        """Remember a canonical transaction for bounded future peer replay."""

        if (
            not isinstance(payload, bytes)
            or len(payload) != Config.TRANSACTION_LENGTH
        ):
            raise ValueError("Pending transaction must be canonical")
        if not isinstance(hash_bytes, bytes) or len(hash_bytes) != 32:
            raise ValueError("Transaction hash must contain exactly 32 bytes")
        self._pending_tx_relays[hash_bytes] = payload
        limit = max(
            1,
            min(Config.KNOWN_INV_LIMIT, Config.PENDING_TX_RELAY_LIMIT),
        )
        while len(self._pending_tx_relays) > limit:
            oldest = next(iter(self._pending_tx_relays))
            self._pending_tx_relays.pop(oldest, None)

    def _snapshot_competing_transactions(self, block: Block) -> list:
        """Capture Redis candidates that block acceptance would orphan."""

        captured = []
        try:
            client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
            )
            confirmed = [
                transaction
                for transaction in block.txns
                if not transaction.is_coinbase
            ]
            if not confirmed:
                return captured
            candidate_ids = client.mget(
                [transaction.mempool_nonce_key for transaction in confirmed]
            )
            if not isinstance(candidate_ids, (list, tuple)) or len(
                candidate_ids
            ) != len(confirmed):
                return captured

            candidates = []
            for transaction, candidate_id in zip(confirmed, candidate_ids):
                try:
                    if isinstance(candidate_id, bytes):
                        candidate_id = candidate_id.decode("ascii")
                    if isinstance(candidate_id, str):
                        binascii.unhexlify(candidate_id)
                except (UnicodeDecodeError, binascii.Error, ValueError):
                    continue
                if candidate_id == transaction.id or not isinstance(
                    candidate_id, str
                ):
                    continue
                if len(candidate_id) != 64:
                    continue
                candidates.append((transaction, candidate_id))
            if not candidates:
                return captured

            payloads = client.mget(
                [candidate_id for _transaction, candidate_id in candidates]
            )
            if not isinstance(payloads, (list, tuple)) or len(payloads) != len(
                candidates
            ):
                return captured
            for (transaction, candidate_id), payload in zip(
                candidates, payloads
            ):
                if not isinstance(payload, bytes):
                    continue
                try:
                    pending = Transaction().deserialize(payload)
                except Exception:
                    continue
                if pending.id != candidate_id:
                    continue
                if (
                    pending.chain,
                    pending.from_address,
                    pending.nonce,
                ) != (
                    transaction.chain,
                    transaction.from_address,
                    transaction.nonce,
                ):
                    continue
                captured.append((pending, payload))
        except Exception:
            log.debug(
                "Unable to snapshot competing mempool slots", exc_info=True
            )
        return captured

    def _forget_confirmed_transactions(
        self, block: Block, captured_evictions: list = None
    ) -> None:
        confirmed_ids = set()
        confirmed_slots = set()
        for transaction in block.txns:
            if transaction.is_coinbase:
                continue
            try:
                hash_bytes = binascii.unhexlify(transaction.id)
            except (binascii.Error, ValueError):
                continue
            confirmed_ids.add(hash_bytes)
            confirmed_slots.add(
                (
                    transaction.chain,
                    transaction.from_address,
                    transaction.nonce,
                )
            )

        redis_evictions = {
            pending.id: (pending, payload)
            for pending, payload in (captured_evictions or [])
        }
        for hash_bytes, payload in list(self._pending_tx_relays.items()):
            try:
                pending = Transaction().deserialize(payload)
            except Exception:
                self._pending_tx_relays.pop(hash_bytes, None)
                continue
            same_slot = (
                pending.chain,
                pending.from_address,
                pending.nonce,
            ) in confirmed_slots
            if hash_bytes in confirmed_ids or same_slot:
                self._pending_tx_relays.pop(hash_bytes, None)
                if binascii.unhexlify(pending.id) == hash_bytes:
                    redis_evictions[pending.id] = (pending, payload)

        if not redis_evictions:
            return
        try:
            client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
            )
            for pending, payload in redis_evictions.values():
                client.eval(
                    _MEMPOOL_EVICT_PENDING_SCRIPT,
                    2,
                    pending.mempool_nonce_key,
                    pending.id,
                    pending.id,
                    payload,
                )
        except Exception:
            # Chain acceptance must not be rolled back because the disposable
            # Redis mempool is unavailable. A later mempool rebuild can discard
            # any remaining orphan payload.
            log.debug("Unable to prune confirmed mempool slots", exc_info=True)

    async def _relay_inventory(
        self,
        inv_type: int,
        hash_bytes: bytes,
        exclude: PeerConnection = None,
    ) -> int:
        if (inv_type, hash_bytes) in self._relayed_invs:
            return 0
        payload = build_inv_payload(inv_type, hash_bytes)
        relay_count = await self._send_to_peers(CMD_INV, payload, exclude)
        if relay_count > 0:
            self._remember_relay(inv_type, hash_bytes)
        return relay_count

    async def _relay_transaction(
        self,
        payload: bytes,
        hash_bytes: bytes,
        exclude: PeerConnection = None,
    ) -> int:
        if (INV_TX, hash_bytes) in self._relayed_invs:
            return 0
        relay_count = await self._send_to_peers(CMD_TX, payload, exclude)
        if relay_count > 0:
            self._remember_relay(INV_TX, hash_bytes)
        return relay_count

    async def _send_to_peers(
        self,
        command: bytes,
        payload: bytes,
        exclude: PeerConnection = None,
    ) -> int:
        seen_peers = set()
        peers = []
        for peer in list(self.peers.values()):
            if peer is exclude:
                continue
            if id(peer) in seen_peers:
                continue
            seen_peers.add(id(peer))
            peers.append(peer)

        async def send_one(peer):
            try:
                await asyncio.wait_for(
                    peer.send(command, payload),
                    timeout=Config.P2P_SEND_TIMEOUT,
                )
                return True
            except (asyncio.TimeoutError, ConnectionError, OSError):
                return False

        results = await asyncio.gather(
            *(send_one(peer) for peer in peers), return_exceptions=True
        )
        relay_count = sum(result is True for result in results)
        for peer, result in zip(peers, results):
            if result is True:
                continue
            if isinstance(result, BaseException):
                log.warning(
                    "Unexpected relay failure for %s:%s",
                    peer.host,
                    peer.port,
                    exc_info=(type(result), result, result.__traceback__),
                )
            try:
                await self._remove_peer(peer, forget=True)
            except Exception:
                log.exception(
                    "Unable to remove failed relay peer %s:%s",
                    peer.host,
                    peer.port,
                )
        return relay_count

    async def _relay_pending_to_peer(
        self, peer: PeerConnection
    ) -> tuple[int, bool]:
        """Replay one bounded, time-budgeted backlog slice to a peer."""

        if not getattr(peer, "connected", False):
            return 0, False
        items = list(self._pending_tx_relays.items())
        if not items:
            self._pending_relay_cursors.pop(peer, None)
            return 0, True

        cursor = self._pending_relay_cursors.get(peer)
        hashes = [hash_bytes for hash_bytes, _payload in items]
        try:
            start = hashes.index(cursor) + 1 if cursor is not None else 0
        except ValueError:
            start = 0
        if start >= len(items):
            start = 0

        batch_size = max(1, int(Config.PENDING_TX_REPLAY_BATCH_SIZE))
        selected = items[start : start + batch_size]
        budget = max(0.001, float(Config.PENDING_TX_REPLAY_BUDGET))
        deadline = asyncio.get_running_loop().time() + budget
        relay_count = 0
        healthy = True

        for hash_bytes, payload in selected:
            if not getattr(peer, "connected", False):
                healthy = False
                break
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(
                    peer.send(CMD_TX, payload),
                    timeout=min(Config.P2P_SEND_TIMEOUT, remaining),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                healthy = False
                log.info(
                    "Pending relay failed for peer %s:%s",
                    peer.host,
                    peer.port,
                    exc_info=True,
                )
                break
            relay_count += 1
            self._pending_relay_cursors[peer] = hash_bytes
            self._remember_relay(INV_TX, hash_bytes)

        if (
            relay_count
            and self._pending_relay_cursors.get(peer) == items[-1][0]
        ):
            # The next maintenance cycle deliberately starts at the beginning,
            # periodically re-announcing a still-pending bounded backlog.
            self._pending_relay_cursors.pop(peer, None)
        return relay_count, healthy

    async def _relay_pending_transactions(self) -> int:
        """Replay pending transactions to every peer after synchronization."""

        seen_peers = set()
        peers = []
        for peer in list(self.peers.values()):
            if id(peer) in seen_peers:
                continue
            seen_peers.add(id(peer))
            peers.append(peer)

        results = await asyncio.gather(
            *(self._relay_pending_to_peer(peer) for peer in peers),
            return_exceptions=True,
        )
        relay_count = 0
        for peer, result in zip(peers, results):
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], int)
            ):
                sent, healthy = result
                relay_count += max(0, sent)
            else:
                healthy = False
                if isinstance(result, BaseException):
                    log.warning(
                        "Unexpected pending relay failure for %s:%s",
                        peer.host,
                        peer.port,
                        exc_info=(
                            type(result),
                            result,
                            result.__traceback__,
                        ),
                    )
            if not healthy:
                try:
                    await self._remove_peer(peer, forget=True)
                except Exception:
                    log.exception(
                        "Unable to remove failed replay peer %s:%s",
                        peer.host,
                        peer.port,
                    )
        return relay_count

    async def broadcast_block(self, block: Block) -> int:
        hash_bytes = binascii.unhexlify(block.id)
        self._forget_confirmed_transactions(block)
        self._remember_inventory(hash_bytes)
        return await self._relay_inventory(INV_BLOCK, hash_bytes)

    async def broadcast_tx(self, tx: Transaction) -> int:
        payload = tx.serialize()
        hash_bytes = binascii.unhexlify(tx.id)
        self._queue_pending_transaction(payload, hash_bytes)
        self._remember_inventory(hash_bytes)
        return await self._relay_transaction(payload, hash_bytes)

    # ------------------------------------------------------------------
    # Peer reader and cleanup
    # ------------------------------------------------------------------

    async def listen_to_peer(self, peer: PeerConnection) -> None:
        """Own the connection's only reads and dispatch every message."""
        try:
            while self.running and peer.connected:
                command, payload = await peer.receive(
                    timeout=max(30.0, self.ping_interval * 3)
                )
                if command is None:
                    break
                await self.handle_message(peer, command, payload)
        except asyncio.CancelledError:
            raise
        except (ProtocolError, ValueError, ConnectionError, OSError):
            log.info("Dropping malformed peer %s:%s", peer.host, peer.port)
        except Exception:
            log.exception(
                "Peer dispatcher failed for %s:%s", peer.host, peer.port
            )
        finally:
            await self._remove_peer(peer)

    async def _remove_peer(
        self, peer: PeerConnection, forget: bool = False
    ) -> None:
        addresses = [
            addr for addr, connected in self.peers.items() if connected is peer
        ]
        remembered = self._peer_addresses.pop(peer, None)
        if remembered is not None and remembered not in addresses:
            addresses.append(remembered)
        for addr in addresses:
            if self.peers.get(addr) is peer:
                self.peers.pop(addr, None)
            if forget:
                self.discovery.remove_peer(*addr)

        current = asyncio.current_task()
        reader_task = self._reader_tasks.pop(peer, None)
        sync_task = self._sync_tasks.pop(peer, None)
        cancelled = []
        for task in (reader_task, sync_task):
            if task is not None and task is not current and not task.done():
                task.cancel()
                cancelled.append(task)
        self._sync_queues.pop(peer, None)
        self._pending_relay_cursors.pop(peer, None)
        for key, future in list(self._pong_waiters.items()):
            if key[0] == id(peer):
                if not future.done():
                    future.cancel()
                self._pong_waiters.pop(key, None)
        await peer.disconnect()
        if cancelled:
            await asyncio.gather(*cancelled, return_exceptions=True)

    # ------------------------------------------------------------------
    # Keep-alive
    # ------------------------------------------------------------------

    async def _ping_loop(self) -> None:
        try:
            while self.running:
                await asyncio.sleep(max(0.1, self.ping_interval))
                if self.running:
                    await self.ping_peers()
        except asyncio.CancelledError:
            raise

    async def _ping_managed_peer(self, peer: PeerConnection) -> bool:
        nonce = secrets.randbits(64)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        key = (id(peer), nonce)
        self._pong_waiters[key] = future
        try:
            await peer.send(CMD_PING, build_ping_payload(nonce))
            await asyncio.wait_for(future, timeout=10.0)
            return True
        except (asyncio.TimeoutError, ConnectionError, OSError):
            return False
        finally:
            self._pong_waiters.pop(key, None)

    async def ping_peers(self) -> None:
        """Ping peers without creating a competing stream reader."""
        async with self._ping_cycle_lock:
            peers = list(self.peers.values())

            async def ping_one(peer):
                if getattr(peer, "_node_managed", False) is True:
                    return await self._ping_managed_peer(peer)
                # Compatibility for standalone/mock peers without a Node
                # reader. Managed connections never take this path.
                try:
                    return await peer.send_ping(secrets.randbits(64))
                except (ConnectionError, OSError, RuntimeError):
                    return False

            results = await asyncio.gather(
                *(ping_one(peer) for peer in peers),
                return_exceptions=True,
            )
            for peer, result in zip(peers, results):
                ok = result is True
                if not ok:
                    log.info(
                        "Peer %s:%s failed ping, disconnecting",
                        peer.host,
                        peer.port,
                    )
                    await self._remove_peer(peer, forget=True)
