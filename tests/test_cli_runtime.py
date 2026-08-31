from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from luracoin.cli import (
    _explorer_api_for_args,
    _parse_seeds,
    _print_service_ready,
    _wallet_web_for_args,
    build_parser,
    cli,
    run_miner,
    run_node,
)
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError


def test_cli_uses_canonical_commands_and_keeps_legacy_aliases():
    parser = build_parser()
    canonical = parser.parse_args(["get-info", "--network", "testnet"])
    legacy = parser.parse_args(["getInfo", "--network", "testnet"])

    assert canonical.command == "get-info"
    assert legacy.command == "getInfo"
    assert canonical.network == legacy.network == "testnet"


def test_seed_parser_validates_ports_and_hosts():
    assert _parse_seeds(["127.0.0.1:9999", "seed.example:19999"]) == [
        ("127.0.0.1", 9999),
        ("seed.example", 19999),
    ]
    with pytest.raises(SystemExit, match="expected HOST:PORT"):
        _parse_seeds(["missing-port"])
    with pytest.raises(SystemExit, match="expected HOST:PORT"):
        _parse_seeds(["host:70000"])


def test_node_and_miner_expose_optional_wallet_web_options():
    parser = build_parser()
    defaults = parser.parse_args(["node"])
    assert defaults.wallet_dir is None
    assert defaults.wallet_host == "127.0.0.1"
    assert defaults.wallet_port == 8080
    assert defaults.explorer_api is True
    assert defaults.explorer_host == "127.0.0.1"
    assert defaults.explorer_port is None
    assert defaults.explorer_index is False
    assert defaults.explorer_db is None

    container = parser.parse_args(
        [
            "mine",
            "--address",
            "address-validation-happens-later",
            "--wallet-dir",
            "/app/wallet",
            "--wallet-host",
            "0.0.0.0",
            "--wallet-port",
            "18080",
        ]
    )
    assert container.wallet_dir == "/app/wallet"
    assert container.wallet_host == "0.0.0.0"
    assert container.wallet_port == 18080

    with pytest.raises(SystemExit):
        parser.parse_args(["node", "--wallet-host", "192.0.2.1"])

    disabled = parser.parse_args(["node", "--no-explorer-api"])
    assert disabled.explorer_api is False

    indexed = parser.parse_args(
        ["node", "--explorer-index", "--api-port", "19000"]
    )
    assert indexed.explorer_index is True
    assert indexed.explorer_port == 19_000


def test_wallet_web_is_disabled_unless_a_dist_directory_is_explicit():
    rpc = SimpleNamespace(host="127.0.0.1", port=18444, token="t" * 48)
    assert _wallet_web_for_args(SimpleNamespace(wallet_dir=None), rpc) is None

    args = SimpleNamespace(
        wallet_dir="/app/wallet",
        wallet_host="0.0.0.0",
        wallet_port=8080,
    )
    with patch("luracoin.cli.WalletWebServer") as server_class:
        result = _wallet_web_for_args(args, rpc)

    assert result is server_class.return_value
    server_class.assert_called_once_with(
        wallet_dir="/app/wallet",
        host="0.0.0.0",
        port=8080,
        rpc_host="127.0.0.1",
        rpc_port=18444,
        rpc_token="t" * 48,
    )


def test_explorer_factory_is_disabled_for_legacy_namespaces():
    assert _explorer_api_for_args(SimpleNamespace(), object()) is None
    with pytest.raises(ValueError, match="requires the explorer API"):
        _explorer_api_for_args(
            SimpleNamespace(explorer_api=False, explorer_index=True),
            object(),
        )


def test_cli_rejects_index_when_explorer_api_is_disabled(capsys):
    with pytest.raises(SystemExit) as error:
        cli(["node", "--no-explorer-api", "--explorer-index"])

    assert error.value.code == 2
    assert (
        "--explorer-index requires --explorer-api" in capsys.readouterr().err
    )


@pytest.mark.asyncio
async def test_mainnet_node_fails_before_binding_without_genesis(
    tmp_path,
    restore_config,
):
    Config.configure(network="mainnet", data_dir=str(tmp_path / "mainnet"))
    args = SimpleNamespace(
        host="127.0.0.1",
        port=9999,
        rpc_host="127.0.0.1",
        rpc_port=8444,
        seed=[],
    )

    with pytest.raises(BlockNotValidError, match="genesis is intentionally"):
        await run_node(args)


@pytest.mark.asyncio
async def test_miner_rejects_invalid_reward_address_before_starting():
    with pytest.raises(SystemExit, match="Invalid Luracoin reward address"):
        await run_miner(SimpleNamespace(address="not-an-address"))


@pytest.mark.asyncio
async def test_node_starts_and_stops_wallet_with_rpc_and_p2p(tmp_path):
    args = SimpleNamespace(
        host="127.0.0.1",
        port=9999,
        rpc_host="127.0.0.1",
        rpc_port=18444,
        seed=[],
        wallet_dir=str(tmp_path),
        wallet_host="127.0.0.1",
        wallet_port=8080,
    )
    node = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
    )
    rpc = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    wallet_web = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    with (
        patch("luracoin.genesis.initialize_chain") as initialize,
        patch("luracoin.network.node.Node", return_value=node),
        patch("luracoin.cli.RpcServer", return_value=rpc),
        patch(
            "luracoin.cli._wallet_web_for_args", return_value=wallet_web
        ) as wallet_factory,
        patch(
            "luracoin.cli._install_signal_handlers",
            side_effect=lambda event: event.set(),
        ),
        patch("luracoin.cli._print_service_ready") as ready,
    ):
        await run_node(args)

    initialize.assert_called_once_with()
    node.start.assert_awaited_once_with()
    rpc.start.assert_awaited_once_with()
    wallet_web.start.assert_awaited_once_with()
    ready.assert_called_once_with(
        node, rpc, wallet_web=wallet_web, mining=False
    )
    wallet_web.stop.assert_awaited_once_with()
    rpc.stop.assert_awaited_once_with()
    node.stop.assert_awaited_once_with()
    wallet_factory.assert_called_once_with(args, rpc)


@pytest.mark.asyncio
async def test_node_starts_and_stops_the_explorer_service():
    args = SimpleNamespace(
        host="127.0.0.1",
        port=9999,
        rpc_host="127.0.0.1",
        rpc_port=18444,
        seed=[],
        wallet_dir=None,
        explorer_api=True,
        explorer_index=True,
    )
    node = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    rpc = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    explorer = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    with (
        patch("luracoin.genesis.initialize_chain"),
        patch("luracoin.network.node.Node", return_value=node),
        patch("luracoin.cli.RpcServer", return_value=rpc),
        patch("luracoin.cli._wallet_web_for_args", return_value=None),
        patch(
            "luracoin.cli._explorer_api_for_args", return_value=explorer
        ) as explorer_factory,
        patch(
            "luracoin.cli._install_signal_handlers",
            side_effect=lambda event: event.set(),
        ),
        patch("luracoin.cli._print_service_ready") as ready,
    ):
        await run_node(args)

    explorer_factory.assert_called_once_with(args, node)
    node.start.assert_awaited_once_with()
    rpc.start.assert_awaited_once_with()
    explorer.start.assert_awaited_once_with()
    ready.assert_called_once_with(
        node,
        rpc,
        wallet_web=None,
        explorer_api=explorer,
        mining=False,
    )
    explorer.stop.assert_awaited_once_with()
    rpc.stop.assert_awaited_once_with()
    node.stop.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_miner_starts_and_stops_wallet_with_rpc(tmp_path):
    args = SimpleNamespace(
        address="valid-address",
        host="127.0.0.1",
        port=9999,
        rpc_host="127.0.0.1",
        rpc_port=18444,
        seed=[],
        wallet_dir=str(tmp_path),
        wallet_host="127.0.0.1",
        wallet_port=8080,
    )
    node = SimpleNamespace(running=True)
    miner = SimpleNamespace(
        node=node,
        start=AsyncMock(),
        stop=AsyncMock(),
    )
    rpc = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    wallet_web = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    with (
        patch("luracoin.wallet.is_valid_address", return_value=True),
        patch("luracoin.network.miner.MiningNode", return_value=miner),
        patch("luracoin.cli.RpcServer", return_value=rpc),
        patch("luracoin.cli._wallet_web_for_args", return_value=wallet_web),
        patch(
            "luracoin.cli._install_signal_handlers",
            side_effect=lambda event: event.set(),
        ),
        patch("luracoin.cli._print_service_ready") as ready,
    ):
        await run_miner(args)

    miner.start.assert_awaited_once_with()
    rpc.start.assert_awaited_once_with()
    wallet_web.start.assert_awaited_once_with()
    ready.assert_called_once_with(
        node, rpc, wallet_web=wallet_web, mining=True
    )
    wallet_web.stop.assert_awaited_once_with()
    rpc.stop.assert_awaited_once_with()
    miner.stop.assert_awaited_once_with()


def test_service_banner_distinguishes_started_from_chain_ready(capsys):
    node = SimpleNamespace(
        ready=False,
        host="127.0.0.1",
        port=9999,
        chain=SimpleNamespace(tip=7),
        best_peer_height=12,
    )
    rpc = SimpleNamespace(host="127.0.0.1", port=18444)

    _print_service_ready(node, rpc, mining=False)

    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["started"] is True
    assert payload["ready"] is False
    assert payload["height"] == 7
    assert payload["best_peer_height"] == 12
    assert payload["wallet"] == {
        "enabled": False,
        "host": None,
        "port": None,
    }


def test_service_banner_reports_wallet_without_secrets(capsys):
    node = SimpleNamespace(
        ready=True,
        host="0.0.0.0",
        port=9999,
        chain=SimpleNamespace(tip=7),
        best_peer_height=7,
    )
    rpc = SimpleNamespace(host="127.0.0.1", port=18444, token="secret")
    wallet_web = SimpleNamespace(host="127.0.0.1", port=8080)

    _print_service_ready(node, rpc, wallet_web=wallet_web, mining=False)

    import json

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["wallet"] == {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 8080,
    }
    assert "secret" not in output


@pytest.fixture
def restore_config():
    names = (
        "NETWORK",
        "CHAIN_ID",
        "MAGIC_BYTES",
        "DATA_PATH",
        "DATA_DIR",
        "BLOCKS_DIR",
        "WALLET_PATH",
        "EXPLORER_DB_PATH",
        "EXPLORER_API_PORT",
        "REDIS_DB",
    )
    previous = {name: getattr(Config, name) for name in names}
    yield
    for name, value in previous.items():
        setattr(Config, name, value)
