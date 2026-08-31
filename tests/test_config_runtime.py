from pathlib import Path

import pytest

from luracoin.config import Config, _environment_bool


@pytest.fixture
def restore_runtime_config():
    values = {
        "NETWORK": Config.NETWORK,
        "CHAIN_ID": Config.CHAIN_ID,
        "MAGIC_BYTES": Config.MAGIC_BYTES,
        "DATA_PATH": Config.DATA_PATH,
        "DATA_DIR": Config.DATA_DIR,
        "BLOCKS_DIR": Config.BLOCKS_DIR,
        "WALLET_PATH": Config.WALLET_PATH,
        "EXPLORER_DB_PATH": Config.EXPLORER_DB_PATH,
        "EXPLORER_API_PORT": Config.EXPLORER_API_PORT,
        "REDIS_DB": Config.REDIS_DB,
    }
    yield
    for name, value in values.items():
        setattr(Config, name, value)


def test_networks_have_distinct_ids_and_magic(
    tmp_path, restore_runtime_config
):
    observed = set()

    for network in ("mainnet", "testnet", "devnet"):
        Config.configure(network=network, data_dir=str(tmp_path / network))
        observed.add((Config.CHAIN_ID, Config.MAGIC_BYTES))

    assert len(observed) == 3


def test_configure_uses_exact_explicit_data_dir(
    tmp_path, restore_runtime_config
):
    node_dir = tmp_path / "node-a"
    Config.configure(network="testnet", data_dir=str(node_dir))
    Config.ensure_data_dirs()

    assert Path(Config.DATA_DIR) == node_dir
    assert Path(Config.BLOCKS_DIR) == node_dir / "blocks"
    assert Path(Config.WALLET_PATH) == node_dir / "wallet.dat"
    assert Config.EXPLORER_DB_PATH == node_dir / "explorer.sqlite3"
    assert (node_dir / "blocks").is_dir()
    assert not Config.EXPLORER_DB_PATH.exists()


def test_configure_honors_environment_data_dir(
    tmp_path, monkeypatch, restore_runtime_config
):
    node_dir = tmp_path / "node-from-environment"
    monkeypatch.setenv("LURACOIN_DATA_DIR", str(node_dir))

    Config.configure(network="testnet")

    assert Config.DATA_PATH == node_dir


def test_configure_rejects_unknown_network(restore_runtime_config):
    with pytest.raises(ValueError, match="Unsupported network"):
        Config.configure(network="production")


def test_explorer_ports_follow_network_unless_overridden(
    tmp_path, monkeypatch, restore_runtime_config
):
    monkeypatch.delenv("LURACOIN_EXPLORER_PORT", raising=False)
    Config.configure(network="devnet", data_dir=str(tmp_path / "devnet"))

    assert Config.EXPLORER_API_PORT == 28_000


def test_environment_bool_is_strict(monkeypatch):
    monkeypatch.setenv("LURACOIN_BOOLEAN_TEST", "yes")
    assert _environment_bool("LURACOIN_BOOLEAN_TEST", False) is True

    monkeypatch.setenv("LURACOIN_BOOLEAN_TEST", "0")
    assert _environment_bool("LURACOIN_BOOLEAN_TEST", True) is False

    monkeypatch.setenv("LURACOIN_BOOLEAN_TEST", "maybe")
    with pytest.raises(ValueError, match="LURACOIN_BOOLEAN_TEST"):
        _environment_bool("LURACOIN_BOOLEAN_TEST", False)


def test_each_test_uses_its_own_pytest_data_directory(tmp_path):
    expected = tmp_path / "data"

    assert Path(Config.DATA_DIR) == expected
    assert Path(Config.DATA_TEST_DIR) == expected
    assert Path(Config.BLOCKS_DIR) == expected / "blocks"
    assert Path(Config.BLOCKS_TEST_DIR) == expected / "blocks"
