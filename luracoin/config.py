"""Runtime configuration for Luracoin.

The original project derived its data directory from the process working
directory. That made the installed CLI write into surprising locations and
made it impossible to run isolated nodes. Configuration is now explicit,
network-aware, and defaults to a per-user testnet directory.
"""

from __future__ import annotations

import binascii
import os
from pathlib import Path
from typing import Optional


def _with_separator(path: Path) -> str:
    return str(path) + os.sep


def _environment_bool(name: str, default: bool) -> bool:
    """Read one strict boolean setting from the environment."""

    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be one of 1/0, true/false, yes/no or on/off"
    )


class Config:
    SOURCE_ROOT = Path(__file__).resolve().parent.parent
    # Kept for compatibility with older tests and callers. Runtime data no
    # longer lives below the source checkout.
    BASE_DIR = str(SOURCE_ROOT)

    NETWORK_CHAIN_IDS = {"mainnet": 0, "testnet": 1, "devnet": 2}
    NETWORK_MAGIC = {
        "mainnet": b"\xba\x77\xd8\x9f",
        "testnet": b"\xfb\xc0\xb6\xdb",
        "devnet": b"\xfa\xce\xb0\x0c",
    }
    NETWORK_REDIS_DB = {"mainnet": 0, "testnet": 1, "devnet": 2}
    NETWORK_EXPLORER_PORTS = {
        "mainnet": 8_000,
        "testnet": 18_000,
        "devnet": 28_000,
    }

    # Safe default: an explicit mainnet launch requires opting in.
    NETWORK = os.environ.get("LURACOIN_NETWORK", "testnet").lower()
    if NETWORK not in NETWORK_CHAIN_IDS:
        raise ValueError(f"Unsupported Luracoin network: {NETWORK}")
    CHAIN_ID = NETWORK_CHAIN_IDS[NETWORK]
    MAGIC_BYTES = NETWORK_MAGIC[NETWORK]

    DEFAULT_DATA_ROOT = Path(
        os.environ.get("LURACOIN_HOME", Path.home() / ".luracoin")
    ).expanduser()
    DATA_PATH = Path(
        os.environ.get("LURACOIN_DATA_DIR", DEFAULT_DATA_ROOT / NETWORK)
    ).expanduser()
    DATA_DIR = _with_separator(DATA_PATH)
    BLOCKS_DIR = _with_separator(DATA_PATH / "blocks")
    WALLET_PATH = str(DATA_PATH / "wallet.dat")
    EXPLORER_DB_PATH = Path(
        os.environ.get("LURACOIN_EXPLORER_DB", DATA_PATH / "explorer.sqlite3")
    ).expanduser()

    # Tests intentionally remain within the source checkout and override the
    # runtime paths from their fixtures.
    DATA_TEST_PATH = SOURCE_ROOT / "tests" / "data"
    DATA_TEST_DIR = _with_separator(DATA_TEST_PATH)
    BLOCKS_TEST_DIR = _with_separator(DATA_TEST_PATH / "blocks")

    COINBASE_UNLOCK_SIGNATURE = binascii.unhexlify("0" * 256)
    STAKING_ADDRESS = "0" * 34
    STARTING_DIFFICULTY = b"\x1d\xff\xff\xff"

    MAX_TX_PER_BLOCK = 65_535
    TRANSACTION_LENGTH = 213
    PORT = 9999

    DATABASE_ACCOUNTS = "accounts.db"
    DATABASE_CHAINSTATE = "chainstate.db"
    DATABASE_BLOCKS = "blocks.db"

    # Max file size of each blkXXXX.dat in bytes (128 MiB).
    MAX_FILE_SIZE = 134_217_728
    MAX_BLOCK_SIZE = {
        0: 10_000,
        28_800: 50_000,
        57_600: 75_000,
        86_400: 200_000,
        172_800: 1_000_000,
        259_200: 2_000_000,
        345_600: 3_000_000,
        432_000: 8_000_000,
    }
    MAX_BLOCK_SERIALIZED_SIZE = 8_000_000
    MAX_P2P_PAYLOAD = MAX_BLOCK_SERIALIZED_SIZE + 4

    TRANSACTION_MATURITY = 1
    MAX_FUTURE_BLOCK_TIME = 500

    LURASHIS_PER_COIN = 100_000_000
    COINS_TO_FORGE = 100_000 * LURASHIS_PER_COIN
    BLOCK_REWARD = 50 * LURASHIS_PER_COIN
    # Once regular halvings would reduce the subsidy below one coin, a
    # permanent tail emission keeps miners incentivised without relying only
    # on transaction fees.
    TAIL_REWARD = 1 * LURASHIS_PER_COIN
    HALVING_BLOCKS = 259_200

    BLOCK_TIME = 180
    DIFFICULTY_ADJUSTMENT_INTERVAL = 480

    SEED_NODES = []
    MAX_PEERS = 8
    MAX_INBOUND_PEERS = 8
    PING_INTERVAL = 60
    P2P_SEND_TIMEOUT = 5.0
    SYNC_PEER_COOLDOWN_BASE = float(
        os.environ.get("LURACOIN_SYNC_COOLDOWN_BASE", "30")
    )
    SYNC_PEER_COOLDOWN_MAX = float(
        os.environ.get("LURACOIN_SYNC_COOLDOWN_MAX", "900")
    )
    SYNC_PEER_COOLDOWN_LIMIT = int(
        os.environ.get("LURACOIN_SYNC_COOLDOWN_LIMIT", "4096")
    )
    SYNC_BATCH_SIZE = 50
    KNOWN_INV_LIMIT = 50_000
    PENDING_TX_RELAY_LIMIT = int(
        os.environ.get("LURACOIN_PENDING_RELAY_LIMIT", "1000")
    )
    PENDING_TX_REPLAY_BATCH_SIZE = int(
        os.environ.get("LURACOIN_REPLAY_BATCH_SIZE", "100")
    )
    PENDING_TX_REPLAY_BUDGET = float(
        os.environ.get("LURACOIN_REPLAY_BUDGET_SECONDS", "5")
    )

    REDIS_HOST = os.environ.get("LURACOIN_REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("LURACOIN_REDIS_PORT", "6379"))
    REDIS_DB = int(
        os.environ.get("LURACOIN_REDIS_DB", str(NETWORK_REDIS_DB[NETWORK]))
    )
    REDIS_DB_TESTS = 9

    # The read-only explorer API is lightweight and enabled on loopback. Its
    # denormalized SQLite index remains an explicit opt-in because it can grow
    # substantially larger than the canonical block files.
    EXPLORER_API_ENABLED = _environment_bool("LURACOIN_EXPLORER_API", True)
    EXPLORER_API_HOST = os.environ.get("LURACOIN_EXPLORER_HOST", "127.0.0.1")
    EXPLORER_API_PORT = int(
        os.environ.get(
            "LURACOIN_EXPLORER_PORT", str(NETWORK_EXPLORER_PORTS[NETWORK])
        )
    )
    EXPLORER_INDEX_ENABLED = _environment_bool(
        "LURACOIN_EXPLORER_INDEX", False
    )
    EXPLORER_INDEX_INTERVAL = float(
        os.environ.get("LURACOIN_EXPLORER_INDEX_INTERVAL", "2")
    )
    if not 1 <= EXPLORER_API_PORT <= 65_535:
        raise ValueError("LURACOIN_EXPLORER_PORT must be between 1 and 65535")
    if EXPLORER_INDEX_INTERVAL <= 0:
        raise ValueError("LURACOIN_EXPLORER_INDEX_INTERVAL must be positive")

    @classmethod
    def configure(
        cls,
        *,
        network: Optional[str] = None,
        data_dir: Optional[str] = None,
    ) -> None:
        """Configure the active network and node data directory.

        ``data_dir`` is treated as the exact directory for this node. When it
        is omitted, data is isolated below ``~/.luracoin/<network>`` (or
        ``LURACOIN_HOME``).
        """

        selected = (network or cls.NETWORK).lower()
        if selected not in cls.NETWORK_CHAIN_IDS:
            valid = ", ".join(sorted(cls.NETWORK_CHAIN_IDS))
            raise ValueError(
                f"Unsupported network {selected!r}; choose {valid}"
            )

        cls.NETWORK = selected
        cls.CHAIN_ID = cls.NETWORK_CHAIN_IDS[selected]
        cls.MAGIC_BYTES = cls.NETWORK_MAGIC[selected]

        configured_data_dir = data_dir or os.environ.get("LURACOIN_DATA_DIR")
        if configured_data_dir:
            path = Path(configured_data_dir).expanduser().resolve()
        else:
            path = cls.DEFAULT_DATA_ROOT / selected
        cls.DATA_PATH = path
        cls.DATA_DIR = _with_separator(path)
        cls.BLOCKS_DIR = _with_separator(path / "blocks")
        cls.WALLET_PATH = str(path / "wallet.dat")
        configured_explorer_db = os.environ.get("LURACOIN_EXPLORER_DB")
        if configured_explorer_db:
            cls.EXPLORER_DB_PATH = (
                Path(configured_explorer_db).expanduser().resolve()
            )
        else:
            cls.EXPLORER_DB_PATH = path / "explorer.sqlite3"

        if "LURACOIN_REDIS_DB" not in os.environ:
            cls.REDIS_DB = cls.NETWORK_REDIS_DB[selected]
        if "LURACOIN_EXPLORER_PORT" not in os.environ:
            cls.EXPLORER_API_PORT = cls.NETWORK_EXPLORER_PORTS[selected]

    @classmethod
    def ensure_data_dirs(cls) -> None:
        """Create the directories required by the configured node."""

        Path(cls.DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.BLOCKS_DIR).mkdir(parents=True, exist_ok=True)

    @classmethod
    def network_summary(cls) -> dict:
        return {
            "network": cls.NETWORK,
            "chain_id": cls.CHAIN_ID,
            "magic": cls.MAGIC_BYTES.hex(),
            "data_dir": cls.DATA_DIR,
        }
