"""Command-line interface for local Luracoin development nodes."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import signal
import sys
from typing import Iterable, Optional

from luracoin import __version__
from luracoin.config import Config
from luracoin.rpc import DEFAULT_RPC_HOST, NETWORK_RPC_PORTS, RpcServer
from luracoin.wallet import generate_wallet
from luracoin.wallet_web import (
    DEFAULT_WALLET_HOST,
    DEFAULT_WALLET_PORT,
    WalletWebServer,
)

COMMAND_ALIASES = {
    "generateWallet": "generate-wallet",
    "getBalance": "get-balance",
    "getBlock": "get-block",
    "getInfo": "get-info",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luracoin",
        description=(
            "Run an educational Luracoin node or inspect its local chain. "
            "Testnet is the safe default."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser(
        "generate-wallet",
        aliases=["generateWallet"],
        help="Generate a BIP39 wallet and print it once as JSON.",
    )
    _add_runtime_options(generate)

    node = commands.add_parser(
        "node", help="Run a P2P node with authenticated loopback RPC."
    )
    _add_runtime_options(node)
    _add_service_options(node)

    mine_parser = commands.add_parser(
        "mine", help="Run a P2P node, RPC, and proof-of-work miner."
    )
    _add_runtime_options(mine_parser)
    _add_service_options(mine_parser)
    mine_parser.add_argument("--address", required=True, help="Reward address")

    balance = commands.add_parser(
        "get-balance",
        aliases=["getBalance"],
        help="Read one account from local chainstate.",
    )
    _add_runtime_options(balance)
    balance.add_argument("address")

    block = commands.add_parser(
        "get-block",
        aliases=["getBlock"],
        help="Read one block by height.",
    )
    _add_runtime_options(block)
    block.add_argument("height", type=_non_negative_int)

    info = commands.add_parser(
        "get-info",
        aliases=["getInfo"],
        help="Show local network and chain status.",
    )
    _add_runtime_options(info)
    return parser


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--network",
        choices=tuple(Config.NETWORK_CHAIN_IDS),
        default=Config.NETWORK,
        help="Network namespace (default: %(default)s)",
    )
    parser.add_argument(
        "--data-dir",
        help="Exact private data directory (default: ~/.luracoin/<network>)",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )


def _add_service_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="0.0.0.0", help="P2P bind address")
    parser.add_argument("--port", type=_port, default=Config.PORT)
    parser.add_argument(
        "--rpc-host",
        choices=("127.0.0.1", "::1", "localhost"),
        default=DEFAULT_RPC_HOST,
    )
    parser.add_argument(
        "--rpc-port",
        type=_port,
        help="Loopback RPC port (network-specific default when omitted)",
    )
    parser.add_argument(
        "--wallet-dir",
        help="Serve this Vite dist directory and enable the wallet gateway",
    )
    parser.add_argument(
        "--wallet-host",
        choices=("127.0.0.1", "0.0.0.0"),
        default=DEFAULT_WALLET_HOST,
        help=(
            "Wallet web bind address; use 0.0.0.0 only inside a container "
            "published to host 127.0.0.1"
        ),
    )
    parser.add_argument(
        "--wallet-port",
        type=_port,
        default=DEFAULT_WALLET_PORT,
        help="Wallet web port (default: %(default)s)",
    )
    explorer_api = parser.add_mutually_exclusive_group()
    explorer_api.add_argument(
        "--explorer-api",
        dest="explorer_api",
        action="store_true",
        help="Enable the read-only block-explorer API (default).",
    )
    explorer_api.add_argument(
        "--no-explorer-api",
        dest="explorer_api",
        action="store_false",
        help="Do not start the read-only block-explorer API.",
    )
    parser.set_defaults(explorer_api=Config.EXPLORER_API_ENABLED)
    parser.add_argument(
        "--explorer-host",
        "--api-host",
        default=Config.EXPLORER_API_HOST,
        help="Explorer API bind address (default: %(default)s)",
    )
    parser.add_argument(
        "--explorer-port",
        "--api-port",
        type=_port,
        help="Explorer API port (network-specific default when omitted)",
    )
    explorer_index = parser.add_mutually_exclusive_group()
    explorer_index.add_argument(
        "--explorer-index",
        dest="explorer_index",
        action="store_true",
        help="Build and follow the optional SQLite explorer index.",
    )
    explorer_index.add_argument(
        "--no-explorer-index",
        dest="explorer_index",
        action="store_false",
        help="Disable the optional SQLite explorer index (default).",
    )
    parser.set_defaults(explorer_index=Config.EXPLORER_INDEX_ENABLED)
    parser.add_argument(
        "--explorer-db",
        help="SQLite index path (default: <data-dir>/explorer.sqlite3)",
    )
    parser.add_argument(
        "--seed",
        action="append",
        default=[],
        metavar="HOST:PORT",
        help="Initial peer; repeat for multiple peers.",
    )


def cli(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.command = COMMAND_ALIASES.get(args.command, args.command)
    if getattr(args, "explorer_index", False) and not getattr(
        args, "explorer_api", False
    ):
        parser.error("--explorer-index requires --explorer-api")
    Config.configure(network=args.network, data_dir=args.data_dir)
    Config.ensure_data_dirs()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "generate-wallet":
        generateWallet()
    elif args.command == "node":
        asyncio.run(run_node(args))
    elif args.command == "mine":
        asyncio.run(run_miner(args))
    elif args.command == "get-balance":
        get_balance(args.address)
    elif args.command == "get-block":
        get_block(args.height)
    elif args.command == "get-info":
        get_info()


async def run_node(args) -> None:
    from luracoin.genesis import initialize_chain
    from luracoin.network.node import Node

    initialize_chain()
    node = Node(
        host=args.host,
        port=args.port,
        seed_nodes=_parse_seeds(args.seed),
    )
    rpc = RpcServer(
        node=node,
        host=args.rpc_host,
        port=args.rpc_port,
    )
    wallet_web = _wallet_web_for_args(args, rpc)
    explorer_api = _explorer_api_for_args(args, node)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    try:
        await node.start()
        await rpc.start()
        if wallet_web is not None:
            await wallet_web.start()
        if explorer_api is not None:
            await explorer_api.start()
            _print_service_ready(
                node,
                rpc,
                wallet_web=wallet_web,
                explorer_api=explorer_api,
                mining=False,
            )
        else:
            _print_service_ready(
                node, rpc, wallet_web=wallet_web, mining=False
            )
        await stop_event.wait()
    finally:
        try:
            if explorer_api is not None:
                await explorer_api.stop()
        finally:
            try:
                if wallet_web is not None:
                    await wallet_web.stop()
            finally:
                try:
                    await rpc.stop()
                finally:
                    await node.stop()


async def run_miner(args) -> None:
    from luracoin.network.miner import MiningNode
    from luracoin.wallet import is_valid_address

    if not is_valid_address(args.address):
        raise SystemExit("Invalid Luracoin reward address.")

    miner = MiningNode(
        address=args.address,
        port=args.port,
        seed_nodes=_parse_seeds(args.seed),
    )
    miner.node.host = args.host
    rpc = RpcServer(
        node=miner.node,
        host=args.rpc_host,
        port=args.rpc_port,
    )
    wallet_web = _wallet_web_for_args(args, rpc)
    explorer_api = _explorer_api_for_args(args, miner.node)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    mining_task = asyncio.create_task(miner.start(), name="luracoin-miner")
    stop_task = asyncio.create_task(stop_event.wait(), name="luracoin-stop")
    try:
        while not miner.node.running and not mining_task.done():
            await asyncio.sleep(0)
        if mining_task.done():
            await mining_task
        await rpc.start()
        if wallet_web is not None:
            await wallet_web.start()
        if explorer_api is not None:
            await explorer_api.start()
            _print_service_ready(
                miner.node,
                rpc,
                wallet_web=wallet_web,
                explorer_api=explorer_api,
                mining=True,
            )
        else:
            _print_service_ready(
                miner.node, rpc, wallet_web=wallet_web, mining=True
            )
        done, _ = await asyncio.wait(
            {mining_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if mining_task in done:
            await mining_task
    finally:
        stop_task.cancel()
        if not mining_task.done():
            mining_task.cancel()
        try:
            if explorer_api is not None:
                await explorer_api.stop()
        finally:
            try:
                if wallet_web is not None:
                    await wallet_web.stop()
            finally:
                try:
                    await rpc.stop()
                finally:
                    try:
                        await miner.stop()
                    finally:
                        await asyncio.gather(
                            mining_task, stop_task, return_exceptions=True
                        )


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signum, stop_event.set)


def _wallet_web_for_args(args, rpc: RpcServer):
    wallet_dir = getattr(args, "wallet_dir", None)
    if not wallet_dir:
        return None
    return WalletWebServer(
        wallet_dir=wallet_dir,
        host=getattr(args, "wallet_host", DEFAULT_WALLET_HOST),
        port=getattr(args, "wallet_port", DEFAULT_WALLET_PORT),
        rpc_host=rpc.host,
        rpc_port=rpc.port,
        rpc_token=rpc.token,
    )


def _explorer_api_for_args(args, node):
    """Build the explorer service without touching SQLite unless enabled."""

    # ``False`` as the compatibility fallback keeps older programmatic callers
    # that construct a partial namespace from unexpectedly opening a socket.
    api_enabled = getattr(args, "explorer_api", False)
    index_enabled = getattr(args, "explorer_index", False)
    if index_enabled and not api_enabled:
        raise ValueError("explorer index requires the explorer API")
    if not api_enabled:
        return None
    from luracoin.explorer_api import ExplorerApiServer

    return ExplorerApiServer(
        node=node,
        host=getattr(args, "explorer_host", Config.EXPLORER_API_HOST),
        port=(
            getattr(args, "explorer_port", None) or Config.EXPLORER_API_PORT
        ),
        index_enabled=index_enabled,
        index_path=(
            getattr(args, "explorer_db", None) or Config.EXPLORER_DB_PATH
        ),
        poll_interval=Config.EXPLORER_INDEX_INTERVAL,
    )


def _print_service_ready(
    node,
    rpc: RpcServer,
    *,
    wallet_web: WalletWebServer = None,
    explorer_api=None,
    mining: bool,
) -> None:
    print(
        json.dumps(
            {
                "started": True,
                "ready": node.ready,
                "network": Config.NETWORK,
                "chain_id": Config.CHAIN_ID,
                "height": node.chain.tip,
                "best_peer_height": node.best_peer_height,
                "p2p": {"host": node.host, "port": node.port},
                "rpc": {"host": rpc.host, "port": rpc.port},
                "wallet": {
                    "enabled": wallet_web is not None,
                    "host": (
                        wallet_web.host if wallet_web is not None else None
                    ),
                    "port": (
                        wallet_web.port if wallet_web is not None else None
                    ),
                },
                "explorer": {
                    "enabled": explorer_api is not None,
                    "host": (
                        explorer_api.host if explorer_api is not None else None
                    ),
                    "port": (
                        explorer_api.port if explorer_api is not None else None
                    ),
                    "index_enabled": bool(
                        explorer_api is not None and explorer_api.index_enabled
                    ),
                },
                "mining": mining,
                "data_dir": Config.DATA_DIR,
            }
        ),
        flush=True,
    )


def generateWallet() -> None:
    print(
        "WARNING: the following recovery material controls the wallet; keep "
        "it private and never use terminal history for funds of value.",
        file=sys.stderr,
    )
    print(json.dumps(generate_wallet(), indent=2))


def get_balance(address: str) -> None:
    from luracoin.chain import Chain
    from luracoin.wallet import is_valid_address

    if not is_valid_address(address):
        raise SystemExit("Invalid Luracoin address.")
    account = Chain().get_account(address) or {"balance": 0, "nonce": 0}
    print(json.dumps({"address": address, **account}, indent=2))


def get_block(height: int) -> None:
    from luracoin.blocks import Block

    block = Block.get(height)
    if block is None:
        raise SystemExit(f"Block {height} not found.")
    print(json.dumps(block.json(), indent=2))


def get_info() -> None:
    from luracoin.chain import Chain
    from luracoin.helpers import mining_reward

    chain = Chain()
    initialized = chain.get_block_file_number(0) is not None
    height = chain.tip if initialized else -1
    print(
        json.dumps(
            {
                **Config.network_summary(),
                "initialized": initialized,
                "height": height,
                "next_block_reward": mining_reward(max(0, height + 1)),
                "rpc_port": NETWORK_RPC_PORTS[Config.NETWORK],
            },
            indent=2,
        )
    )


def _parse_seeds(values: Iterable[str]) -> list:
    seeds = []
    for value in values:
        try:
            host, raw_port = value.rsplit(":", 1)
            port = _port(raw_port)
        except (AttributeError, ValueError, argparse.ArgumentTypeError) as exc:
            raise SystemExit(
                f"Invalid seed {value!r}; expected HOST:PORT."
            ) from exc
        if not host or any(character.isspace() for character in host):
            raise SystemExit(f"Invalid seed host in {value!r}.")
        seeds.append((host, port))
    return seeds


def _port(value) -> int:
    port = int(value)
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _non_negative_int(value) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return number


if __name__ == "__main__":
    cli()
