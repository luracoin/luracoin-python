"""Optional, rebuildable SQLite index for block-explorer queries.

The canonical chain remains the block files and RocksDB state managed by
``Block.save``.  This module deliberately follows that state after the fact:
an indexing failure must never make an otherwise valid block fail.

Constructing :class:`ExplorerIndex` has no filesystem side effects.  Call
:meth:`ExplorerIndex.initialize` explicitly before backfilling or querying it.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from dataclasses import dataclass
from itertools import chain as iter_chain
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config

SCHEMA_VERSION = 1
DEFAULT_DATABASE_NAME = "explorer.sqlite3"
DEFAULT_BATCH_SIZE = 100
DEFAULT_POLL_INTERVAL = 1.0
MAX_PAGE_SIZE = 200
ZERO_ADDRESS = "0" * 34

log = logging.getLogger(__name__)


class ExplorerIndexError(RuntimeError):
    """Base error raised by the optional explorer index."""


class ExplorerIndexNotInitialized(ExplorerIndexError):
    """The index was used before :meth:`ExplorerIndex.initialize`."""


class ExplorerNetworkMismatch(ExplorerIndexError):
    """An index belongs to a different network or chain id."""


class ExplorerSchemaError(ExplorerIndexError):
    """The on-disk schema is unsupported or malformed."""


class ExplorerChainDivergence(ExplorerIndexError):
    """Indexed data and canonical block data do not form the same chain."""


class _ExplorerStopRequested(Exception):
    """Internal control flow used to roll back an interrupted batch."""


@dataclass
class _AddressState:
    balance: int = 0
    nonce: int = 0
    total_received: int = 0
    total_sent: int = 0
    total_fees: int = 0
    transaction_count: int = 0
    first_seen_height: Optional[int] = None
    last_seen_height: Optional[int] = None

    def touch(self, height: int) -> None:
        if self.first_seen_height is None:
            self.first_seen_height = height
        self.last_seen_height = height
        self.transaction_count += 1


_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    height INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    prev_block_hash TEXT NOT NULL,
    miner TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    bits TEXT NOT NULL,
    nonce INTEGER NOT NULL,
    version INTEGER NOT NULL,
    transaction_count INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    total_fees TEXT NOT NULL,
    total_transferred TEXT NOT NULL,
    reward TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS blocks_timestamp_idx
    ON blocks(timestamp DESC, height DESC);
CREATE INDEX IF NOT EXISTS blocks_miner_idx
    ON blocks(miner, height DESC);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    block_height INTEGER NOT NULL,
    tx_index INTEGER NOT NULL,
    chain_id INTEGER NOT NULL,
    nonce INTEGER NOT NULL,
    fee TEXT NOT NULL,
    value TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    is_coinbase INTEGER NOT NULL CHECK (is_coinbase IN (0, 1)),
    UNIQUE(block_height, tx_index),
    FOREIGN KEY(block_height) REFERENCES blocks(height) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS transactions_location_idx
    ON transactions(block_height DESC, tx_index DESC);
CREATE INDEX IF NOT EXISTS transactions_sender_idx
    ON transactions(from_address, block_height DESC, tx_index DESC);
CREATE INDEX IF NOT EXISTS transactions_receiver_idx
    ON transactions(to_address, block_height DESC, tx_index DESC);

CREATE TABLE IF NOT EXISTS addresses (
    address TEXT PRIMARY KEY,
    balance TEXT NOT NULL,
    nonce INTEGER NOT NULL,
    total_received TEXT NOT NULL,
    total_sent TEXT NOT NULL,
    total_fees TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    first_seen_height INTEGER NOT NULL,
    last_seen_height INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS addresses_activity_idx
    ON addresses(last_seen_height DESC, address);

CREATE TABLE IF NOT EXISTS address_transactions (
    address TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    block_height INTEGER NOT NULL,
    tx_index INTEGER NOT NULL,
    direction TEXT NOT NULL
        CHECK (direction IN ('sent', 'received', 'self', 'mined')),
    PRIMARY KEY(address, transaction_id),
    FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS address_transactions_history_idx
    ON address_transactions(address, block_height DESC, tx_index DESC);

CREATE TABLE IF NOT EXISTS chain_stats (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    block_count INTEGER NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_fees TEXT NOT NULL,
    total_transferred TEXT NOT NULL,
    total_rewards TEXT NOT NULL
);
"""


class ExplorerIndex:
    """A local SQLite projection of canonical Luracoin block data.

    ``__init__`` only captures configuration.  The database file, parent
    directory and SQLite sidecar files are created exclusively by
    :meth:`initialize`.
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        *,
        network: Optional[str] = None,
        chain_id: Optional[int] = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self.path = Path(path or Config.EXPLORER_DB_PATH).expanduser()
        self.network = Config.NETWORK if network is None else str(network)
        self.chain_id = Config.CHAIN_ID if chain_id is None else int(chain_id)
        self.busy_timeout_ms = int(busy_timeout_ms)
        if not self.network:
            raise ValueError("network must not be empty")
        if not 0 <= self.chain_id <= 255:
            raise ValueError("chain_id must fit in one byte")
        if self.busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")

        self._connection: Optional[sqlite3.Connection] = None
        self._connection_lock = threading.RLock()
        self._backfill_lock = threading.Lock()

    @property
    def initialized(self) -> bool:
        return self._connection is not None

    def initialize(self) -> "ExplorerIndex":
        """Create/open the database and validate its network identity."""

        with self._connection_lock:
            if self._connection is not None:
                return self

            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path),
                timeout=self.busy_timeout_ms / 1_000,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(
                    "PRAGMA busy_timeout = %d" % self.busy_timeout_ms
                )
                connection.execute("PRAGMA journal_mode = WAL").fetchone()
                connection.execute("PRAGMA synchronous = NORMAL")
                self._initialize_schema(connection)
                self._validate_or_set_identity(connection)
            except Exception:
                connection.close()
                raise

            self._connection = connection
        return self

    def close(self) -> None:
        """Close SQLite resources without deleting the rebuildable index."""

        with self._connection_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def __enter__(self) -> "ExplorerIndex":
        return self.initialize()

    def __exit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc: Optional[BaseException],
        _traceback: Optional[TracebackType],
    ) -> None:
        self.close()

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        user_version = int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        )
        if user_version not in (0, SCHEMA_VERSION):
            raise ExplorerSchemaError(
                "unsupported explorer schema version " f"{user_version}"
            )

        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute("""
            INSERT OR IGNORE INTO chain_stats(
                singleton, block_count, transaction_count, total_fees,
                total_transferred, total_rewards
            ) VALUES (1, 0, 0, '0', '0', '0')
            """)
        connection.commit()

    def _validate_or_set_identity(
        self, connection: sqlite3.Connection
    ) -> None:
        existing = {
            row["key"]: row["value"]
            for row in connection.execute(
                "SELECT key, value FROM metadata"
            ).fetchall()
        }
        if not existing:
            values = {
                "schema_version": str(SCHEMA_VERSION),
                "network": self.network,
                "chain_id": str(self.chain_id),
                "indexed_height": "-1",
                "indexed_block_id": "",
            }
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                values.items(),
            )
            connection.commit()
            return

        required = {
            "schema_version",
            "network",
            "chain_id",
            "indexed_height",
            "indexed_block_id",
        }
        if not required.issubset(existing):
            raise ExplorerSchemaError("explorer metadata is incomplete")
        try:
            stored_schema = int(existing["schema_version"])
            stored_chain_id = int(existing["chain_id"])
            int(existing["indexed_height"])
        except ValueError as exc:
            raise ExplorerSchemaError(
                "explorer metadata is malformed"
            ) from exc
        if stored_schema != SCHEMA_VERSION:
            raise ExplorerSchemaError(
                "unsupported explorer metadata version " f"{stored_schema}"
            )
        if (
            existing["network"] != self.network
            or stored_chain_id != self.chain_id
        ):
            raise ExplorerNetworkMismatch(
                "explorer database belongs to "
                f"{existing['network']} (chain {stored_chain_id}), not "
                f"{self.network} (chain {self.chain_id})"
            )

    def get_metadata(self) -> dict:
        """Return typed schema, network and indexed-tip metadata."""

        connection = self._require_connection()
        with self._connection_lock:
            values = {
                row["key"]: row["value"]
                for row in connection.execute(
                    "SELECT key, value FROM metadata"
                ).fetchall()
            }
        try:
            indexed_height = int(values["indexed_height"])
            chain_id = int(values["chain_id"])
            schema_version = int(values["schema_version"])
        except (KeyError, ValueError) as exc:
            raise ExplorerSchemaError(
                "explorer metadata is malformed"
            ) from exc
        block_id = values.get("indexed_block_id") or None
        return {
            "schema_version": schema_version,
            "network": values.get("network"),
            "chain_id": chain_id,
            "indexed_height": indexed_height,
            "indexed_block_id": block_id,
        }

    def backfill(
        self,
        chain: Optional[Any] = None,
        block_cls: Any = Block,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        stop_requested: Optional[Callable[[], bool]] = None,
    ) -> int:
        """Index every missing canonical block, returning the number added.

        Existing progress is verified before new work begins.  If the indexed
        tip is above the canonical tip or its hash differs, all derived rows
        are cleared and rebuilt automatically.  Each block is one SQLite
        transaction, so a process interruption resumes from the previous
        committed block while ``batch_size`` bounds each tip-reading window.
        """

        self._require_connection()
        chain = Chain() if chain is None else chain
        batch_size = _validated_batch_size(batch_size)

        with self._backfill_lock:
            rebuilt = self._reconcile(chain, block_cls)
            try:
                return self._append_missing(
                    chain, block_cls, batch_size, stop_requested
                )
            except ExplorerChainDivergence:
                # A missing or malformed *next* block does not prove that the
                # already indexed prefix diverged.  Revalidate that prefix and
                # rebuild only when its tip actually changed; otherwise retain
                # all completed work and let the next poll retry the extension.
                if rebuilt or not self._reconcile(chain, block_cls):
                    raise
                return self._append_missing(
                    chain, block_cls, batch_size, stop_requested
                )

    def _reconcile(self, chain: Any, block_cls: Any) -> bool:
        metadata = self.get_metadata()
        indexed_height = metadata["indexed_height"]
        if indexed_height < 0:
            if metadata["indexed_block_id"] is not None:
                self._reset_derived_data()
                return True
            return False

        canonical_tip = _canonical_tip(chain)
        if indexed_height > canonical_tip:
            self._reset_derived_data()
            return True

        indexed_block = _get_many(block_cls, [indexed_height]).get(
            indexed_height
        )
        if (
            indexed_block is None
            or _block_id(indexed_block) != metadata["indexed_block_id"]
        ):
            self._reset_derived_data()
            return True
        return False

    def _append_missing(
        self,
        chain: Any,
        block_cls: Any,
        batch_size: int,
        stop_requested: Optional[Callable[[], bool]],
    ) -> int:
        indexed_count = 0
        while True:
            if stop_requested is not None and stop_requested():
                return indexed_count
            metadata = self.get_metadata()
            start = metadata["indexed_height"] + 1
            canonical_tip = _canonical_tip(chain)
            if start > canonical_tip:
                return indexed_count

            stop = min(start + batch_size - 1, canonical_tip)
            heights = list(range(start, stop + 1))
            for height in heights:
                if stop_requested is not None and stop_requested():
                    return indexed_count
                # Stream one canonical block at a time.  A protocol-sized
                # page can contain very large blocks, so materializing a full
                # backfill batch would create an avoidable memory spike.
                block = _get_many(block_cls, [height]).get(height)
                if block is None:
                    raise ExplorerChainDivergence(
                        f"canonical block {height} is missing"
                    )
                try:
                    self._index_batch(
                        [block],
                        expected_start=height,
                        stop_requested=stop_requested,
                    )
                except _ExplorerStopRequested:
                    return indexed_count
                indexed_count += 1

    def _index_batch(
        self,
        blocks: Iterable[Any],
        *,
        expected_start: int,
        stop_requested: Optional[Callable[[], bool]] = None,
    ) -> None:
        connection = self._require_connection()
        ordered = list(blocks)
        if not ordered:
            return

        with self._connection_lock:
            try:
                connection.execute("BEGIN IMMEDIATE")
                # SQLite's write lock must be held before reading progress and
                # aggregates.  The in-process lock is per ExplorerIndex
                # instance; BEGIN IMMEDIATE also serializes a second instance
                # or process that points at the same derived database.
                current = self._metadata_value(connection, "indexed_height")
                try:
                    current_height = int(current)
                except (TypeError, ValueError) as exc:
                    raise ExplorerSchemaError(
                        "indexed height metadata is malformed"
                    ) from exc
                if current_height + 1 != expected_start:
                    raise ExplorerChainDivergence(
                        "explorer progress changed during backfill"
                    )

                address_states: Dict[str, _AddressState] = {}
                previous_id = self._metadata_value(
                    connection, "indexed_block_id"
                )
                stats = connection.execute(
                    "SELECT * FROM chain_stats WHERE singleton = 1"
                ).fetchone()
                if stats is None:
                    raise ExplorerSchemaError("explorer stats row is missing")
                block_count = int(stats["block_count"])
                transaction_count = int(stats["transaction_count"])
                total_fees = _decimal_to_int(stats["total_fees"])
                total_transferred = _decimal_to_int(stats["total_transferred"])
                total_rewards = _decimal_to_int(stats["total_rewards"])

                next_height = expected_start
                for block in ordered:
                    if stop_requested is not None and stop_requested():
                        raise _ExplorerStopRequested()
                    height = _non_negative_int(block.height, "block height")
                    if height != next_height:
                        raise ExplorerChainDivergence(
                            f"expected block {next_height}, got {height}"
                        )
                    block_identifier = _block_id(block)
                    prev_block_hash = _hash_text(
                        block.prev_block_hash, "previous block hash"
                    )
                    if height == 0:
                        if prev_block_hash != "0" * 64:
                            raise ExplorerChainDivergence(
                                "genesis previous hash is not zero"
                            )
                    elif prev_block_hash != previous_id:
                        raise ExplorerChainDivergence(
                            f"block {height} does not extend the indexed tip"
                        )

                    block_totals = self._insert_block(
                        connection,
                        block,
                        block_identifier,
                        address_states,
                        stop_requested=stop_requested,
                    )
                    block_count += 1
                    transaction_count += block_totals["transaction_count"]
                    total_fees += block_totals["fees"]
                    total_transferred += block_totals["transferred"]
                    total_rewards += block_totals["rewards"]
                    previous_id = block_identifier
                    next_height += 1

                self._write_address_states(connection, address_states)
                connection.execute(
                    """
                    UPDATE chain_stats
                    SET block_count = ?, transaction_count = ?,
                        total_fees = ?, total_transferred = ?,
                        total_rewards = ?
                    WHERE singleton = 1
                    """,
                    (
                        block_count,
                        transaction_count,
                        str(total_fees),
                        str(total_transferred),
                        str(total_rewards),
                    ),
                )
                final_height = next_height - 1
                self._set_metadata(
                    connection, "indexed_height", str(final_height)
                )
                self._set_metadata(connection, "indexed_block_id", previous_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _insert_block(
        self,
        connection: sqlite3.Connection,
        block: Any,
        block_identifier: str,
        address_states: Dict[str, _AddressState],
        *,
        stop_requested: Optional[Callable[[], bool]] = None,
    ) -> dict:
        height = int(block.height)
        transactions = list(block.txns)
        if not transactions or not _is_coinbase(transactions[0]):
            raise ExplorerChainDivergence(
                f"block {height} has no leading coinbase transaction"
            )
        regular_fees = 0
        transferred = 0
        rewards = 0

        for transaction in transactions:
            if stop_requested is not None and stop_requested():
                raise _ExplorerStopRequested()
            value = _uint64(transaction.value, "transaction value")
            fee = _uint64(transaction.fee, "transaction fee")
            if _is_coinbase(transaction):
                rewards += value
            else:
                regular_fees += fee
                transferred += value

        bits = (
            block.bits.hex()
            if isinstance(block.bits, bytes)
            else str(block.bits)
        )
        try:
            size_bytes = len(block.serialize())
        except (AttributeError, TypeError):
            size_bytes = 118 + len(transactions) * Config.TRANSACTION_LENGTH

        connection.execute(
            """
            INSERT INTO blocks(
                height, id, prev_block_hash, miner, timestamp, bits, nonce,
                version, transaction_count, size_bytes, total_fees,
                total_transferred, reward
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                height,
                block_identifier,
                _hash_text(block.prev_block_hash, "previous block hash"),
                str(block.miner),
                _non_negative_int(block.timestamp, "block timestamp"),
                bits,
                _non_negative_int(block.nonce, "block nonce"),
                _non_negative_int(block.version, "block version"),
                len(transactions),
                _non_negative_int(size_bytes, "serialized block size"),
                str(regular_fees),
                str(transferred),
                str(rewards),
            ),
        )

        # Consensus applies regular transfers first and credits the coinbase
        # afterwards.  Preserve the original transaction indexes in SQLite,
        # but mirror that state-transition order so an account can spend down
        # before receiving a reward without causing a false uint64 overflow.
        transaction_indexes = iter_chain(range(1, len(transactions)), (0,))
        for tx_index in transaction_indexes:
            if stop_requested is not None and stop_requested():
                raise _ExplorerStopRequested()
            transaction = transactions[tx_index]
            self._insert_transaction(
                connection,
                transaction,
                block_height=height,
                tx_index=tx_index,
                address_states=address_states,
            )

        return {
            "transaction_count": len(transactions),
            "fees": regular_fees,
            "transferred": transferred,
            "rewards": rewards,
        }

    def _insert_transaction(
        self,
        connection: sqlite3.Connection,
        transaction: Any,
        *,
        block_height: int,
        tx_index: int,
        address_states: Dict[str, _AddressState],
    ) -> None:
        transaction_id = _hash_text(transaction.id, "transaction id")
        value = _uint64(transaction.value, "transaction value")
        fee = _uint64(transaction.fee, "transaction fee")
        sender = str(transaction.from_address)
        receiver = str(transaction.to_address)
        coinbase = _is_coinbase(transaction)

        connection.execute(
            """
            INSERT INTO transactions(
                id, block_height, tx_index, chain_id, nonce, fee, value,
                from_address, to_address, is_coinbase
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                block_height,
                tx_index,
                _non_negative_int(transaction.chain, "transaction chain id"),
                _non_negative_int(transaction.nonce, "transaction nonce"),
                str(fee),
                str(value),
                sender,
                receiver,
                int(coinbase),
            ),
        )

        involved: Dict[str, str] = {}
        if coinbase:
            recipient = self._address_state(
                connection, address_states, receiver
            )
            recipient.balance = _checked_balance(recipient.balance + value)
            recipient.total_received += value
            involved[receiver] = "mined"
        else:
            source = self._address_state(connection, address_states, sender)
            debit = value + fee
            if source.balance < debit:
                raise ExplorerChainDivergence(
                    f"transaction {transaction_id} overdraws {sender}"
                )
            source.balance -= debit
            source.nonce = _non_negative_int(
                transaction.nonce, "transaction nonce"
            )
            source.total_sent += value
            source.total_fees += fee

            target = self._address_state(connection, address_states, receiver)
            target.balance = _checked_balance(target.balance + value)
            target.total_received += value
            if sender == receiver:
                involved[sender] = "self"
            else:
                involved[sender] = "sent"
                involved[receiver] = "received"

        for address, direction in involved.items():
            state = self._address_state(connection, address_states, address)
            state.touch(block_height)
            connection.execute(
                """
                INSERT INTO address_transactions(
                    address, transaction_id, block_height, tx_index, direction
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    address,
                    transaction_id,
                    block_height,
                    tx_index,
                    direction,
                ),
            )

    def _address_state(
        self,
        connection: sqlite3.Connection,
        states: Dict[str, _AddressState],
        address: str,
    ) -> _AddressState:
        if address == ZERO_ADDRESS:
            raise ExplorerChainDivergence(
                "zero address cannot be an indexed account"
            )
        if address in states:
            return states[address]
        row = connection.execute(
            "SELECT * FROM addresses WHERE address = ?", (address,)
        ).fetchone()
        if row is None:
            state = _AddressState()
        else:
            state = _AddressState(
                balance=_uint64(row["balance"], "address balance"),
                nonce=_non_negative_int(row["nonce"], "address nonce"),
                total_received=_decimal_to_int(row["total_received"]),
                total_sent=_decimal_to_int(row["total_sent"]),
                total_fees=_decimal_to_int(row["total_fees"]),
                transaction_count=_non_negative_int(
                    row["transaction_count"], "address transaction count"
                ),
                first_seen_height=_non_negative_int(
                    row["first_seen_height"], "first seen height"
                ),
                last_seen_height=_non_negative_int(
                    row["last_seen_height"], "last seen height"
                ),
            )
        states[address] = state
        return state

    @staticmethod
    def _write_address_states(
        connection: sqlite3.Connection,
        states: Dict[str, _AddressState],
    ) -> None:
        for address, state in states.items():
            if (
                state.first_seen_height is None
                or state.last_seen_height is None
            ):
                raise ExplorerSchemaError(
                    "address activity metadata is missing"
                )
            connection.execute(
                """
                INSERT INTO addresses(
                    address, balance, nonce, total_received, total_sent,
                    total_fees, transaction_count, first_seen_height,
                    last_seen_height
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    balance = excluded.balance,
                    nonce = excluded.nonce,
                    total_received = excluded.total_received,
                    total_sent = excluded.total_sent,
                    total_fees = excluded.total_fees,
                    transaction_count = excluded.transaction_count,
                    first_seen_height = excluded.first_seen_height,
                    last_seen_height = excluded.last_seen_height
                """,
                (
                    address,
                    str(_checked_balance(state.balance)),
                    state.nonce,
                    str(state.total_received),
                    str(state.total_sent),
                    str(state.total_fees),
                    state.transaction_count,
                    state.first_seen_height,
                    state.last_seen_height,
                ),
            )

    def _reset_derived_data(self) -> None:
        connection = self._require_connection()
        with self._connection_lock:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM address_transactions")
                connection.execute("DELETE FROM transactions")
                connection.execute("DELETE FROM addresses")
                connection.execute("DELETE FROM blocks")
                connection.execute("""
                    UPDATE chain_stats
                    SET block_count = 0, transaction_count = 0,
                        total_fees = '0', total_transferred = '0',
                        total_rewards = '0'
                    WHERE singleton = 1
                    """)
                self._set_metadata(connection, "indexed_height", "-1")
                self._set_metadata(connection, "indexed_block_id", "")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list_blocks(self, limit: int = 50, offset: int = 0) -> dict:
        """Return newest blocks as ``{"items": ..., "total": ...}``."""

        limit, offset = _validated_page(limit, offset)
        connection = self._require_connection()
        with self._connection_lock:
            total = int(
                connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT * FROM blocks
                ORDER BY height DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return {"items": [_block_row(row) for row in rows], "total": total}

    def list_transactions(self, limit: int = 50, offset: int = 0) -> dict:
        """Return newest global transactions with stable offset pagination."""

        limit, offset = _validated_page(limit, offset)
        connection = self._require_connection()
        with self._connection_lock:
            indexed_height = int(
                self._metadata_value(connection, "indexed_height") or -1
            )
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM transactions"
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT t.*, b.id AS block_id,
                       b.timestamp AS block_timestamp
                FROM transactions AS t
                JOIN blocks AS b ON b.height = t.block_height
                ORDER BY t.block_height DESC, t.tx_index DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return {
            "items": [
                _transaction_row(row, indexed_height=indexed_height)
                for row in rows
            ],
            "total": total,
        }

    def list_addresses(self, limit: int = 50, offset: int = 0) -> dict:
        """Return the richest addresses using exact decimal-text ordering."""

        limit, offset = _validated_page(limit, offset)
        connection = self._require_connection()
        with self._connection_lock:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM addresses"
                ).fetchone()[0]
            )
            # Canonical decimal strings contain no leading zeroes.  Ordering by
            # length and then lexicographically is therefore exact for uint64
            # balances without casting through SQLite's signed INTEGER range.
            rows = connection.execute(
                """
                SELECT * FROM addresses
                ORDER BY LENGTH(balance) DESC, balance DESC, address ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return {
            "items": [_address_row(row) for row in rows],
            "total": total,
        }

    def get_address_transactions(
        self, address: str, limit: int = 50, offset: int = 0
    ) -> dict:
        """Return one address's newest confirmed transactions."""

        limit, offset = _validated_page(limit, offset)
        address = str(address)
        connection = self._require_connection()
        with self._connection_lock:
            indexed_height = int(
                self._metadata_value(connection, "indexed_height") or -1
            )
            total = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM address_transactions
                    WHERE address = ?
                    """,
                    (address,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT t.*, b.id AS block_id,
                       b.timestamp AS block_timestamp, a.direction
                FROM address_transactions AS a
                JOIN transactions AS t ON t.id = a.transaction_id
                JOIN blocks AS b ON b.height = t.block_height
                WHERE a.address = ?
                ORDER BY a.block_height DESC, a.tx_index DESC
                LIMIT ? OFFSET ?
                """,
                (address, limit, offset),
            ).fetchall()
        items = []
        for row in rows:
            item = _transaction_row(row, indexed_height=indexed_height)
            item["direction"] = row["direction"]
            items.append(item)
        return {"items": items, "total": total}

    def get_stats(self) -> dict:
        """Return exact aggregate strings and current indexed-tip status."""

        connection = self._require_connection()
        with self._connection_lock:
            # Keep metadata and aggregates in the same logical snapshot.  A
            # backfill transaction updates both under this lock and commits
            # them
            # together, so callers must not observe an old tip with new totals.
            metadata = self.get_metadata()
            row = connection.execute(
                "SELECT * FROM chain_stats WHERE singleton = 1"
            ).fetchone()
            address_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM addresses"
                ).fetchone()[0]
            )
        if row is None:
            raise ExplorerSchemaError("explorer stats row is missing")
        return {
            "network": metadata["network"],
            "chain_id": metadata["chain_id"],
            "indexed_height": metadata["indexed_height"],
            "indexed_block_id": metadata["indexed_block_id"],
            "blocks": int(row["block_count"]),
            "transactions": int(row["transaction_count"]),
            "addresses": address_count,
            "total_fees": _decimal_text(row["total_fees"]),
            "total_transferred": _decimal_text(row["total_transferred"]),
            "total_rewards": _decimal_text(row["total_rewards"]),
        }

    def _require_connection(self) -> sqlite3.Connection:
        connection = self._connection
        if connection is None:
            raise ExplorerIndexNotInitialized(
                "call ExplorerIndex.initialize() before using the index"
            )
        return connection

    @staticmethod
    def _metadata_value(
        connection: sqlite3.Connection, key: str
    ) -> Optional[str]:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    @staticmethod
    def _set_metadata(
        connection: sqlite3.Connection, key: str, value: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


class ExplorerIndexer:
    """Async polling follower for an explicitly initialized index."""

    def __init__(
        self,
        index: ExplorerIndex,
        *,
        chain: Optional[Any] = None,
        block_cls: Any = Block,
        batch_size: int = DEFAULT_BATCH_SIZE,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.index = index
        self.chain = Chain() if chain is None else chain
        self.block_cls = block_cls
        self.batch_size = _validated_batch_size(batch_size)
        self.poll_interval = float(poll_interval)
        if self.poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.last_error: Optional[BaseException] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._thread_stop_event = threading.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> int:
        """Perform one non-blocking catch-up pass."""

        if not self.index.initialized:
            raise ExplorerIndexNotInitialized(
                "initialize the ExplorerIndex before starting its follower"
            )
        indexed = await asyncio.to_thread(
            self.index.backfill,
            self.chain,
            self.block_cls,
            batch_size=self.batch_size,
            stop_requested=self._thread_stop_event.is_set,
        )
        self.last_error = None
        return indexed

    async def start(self) -> None:
        """Start polling; this never creates the database implicitly."""

        if self.running:
            return
        if not self.index.initialized:
            raise ExplorerIndexNotInitialized(
                "initialize the ExplorerIndex before starting its follower"
            )
        self._stop_event = asyncio.Event()
        self._thread_stop_event.clear()
        self._task = asyncio.create_task(
            self._run(), name="luracoin-explorer-indexer"
        )

    async def stop(self) -> None:
        """Stop polling without closing the caller-owned index."""

        task = self._task
        stop_event = self._stop_event
        if task is None:
            return
        if stop_event is not None:
            stop_event.set()
        self._thread_stop_event.set()
        try:
            await task
        finally:
            self._task = None
            self._stop_event = None
            self._thread_stop_event.clear()

    async def _run(self) -> None:
        stop_event = self._stop_event
        if stop_event is None:
            return
        consecutive_failures = 0
        while not stop_event.is_set():
            delay = self.poll_interval
            try:
                await self.run_once()
                consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # The canonical node keeps running.  The next poll retries from
                # the last SQLite block that committed successfully.
                self.last_error = exc
                consecutive_failures += 1
                delay = min(
                    self.poll_interval
                    * (2 ** min(consecutive_failures - 1, 5)),
                    60.0,
                )
                log.exception(
                    "Explorer indexing pass failed; retrying in %.1fs", delay
                )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass


def _canonical_tip(chain: Any) -> int:
    getter = getattr(chain, "get_block_file_number", None)
    if getter is not None and getter(0) is None:
        return -1
    tip = int(chain.tip)
    if tip < 0:
        return -1
    return tip


def _get_many(block_cls: Any, heights: List[int]) -> Dict[int, Any]:
    result = block_cls.get_many(heights)
    if not isinstance(result, dict):
        raise ExplorerChainDivergence("Block.get_many returned invalid data")
    return result


def _block_id(block: Any) -> str:
    return _hash_text(block.id, "block id")


def _hash_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ExplorerChainDivergence(f"{label} is not a 32-byte hex string")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ExplorerChainDivergence(
            f"{label} is not a 32-byte hex string"
        ) from exc
    return value.lower()


def _is_coinbase(transaction: Any) -> bool:
    return bool(getattr(transaction, "is_coinbase", False)) or (
        getattr(transaction, "from_address", None) == ZERO_ADDRESS
    )


def _uint64(value: Any, label: str) -> int:
    number = _non_negative_int(value, label)
    if number > 0xFFFFFFFFFFFFFFFF:
        raise ExplorerChainDivergence(f"{label} exceeds uint64")
    return number


def _checked_balance(value: int) -> int:
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ExplorerChainDivergence("indexed account balance exceeds uint64")
    return value


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ExplorerChainDivergence(f"{label} is not an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerChainDivergence(f"{label} is not an integer") from exc
    if number < 0:
        raise ExplorerChainDivergence(f"{label} must not be negative")
    return number


def _decimal_to_int(value: Any) -> int:
    text = _decimal_text(value)
    return int(text)


def _decimal_text(value: Any) -> str:
    text = str(value)
    if not text or not text.isascii() or not text.isdigit():
        raise ExplorerSchemaError("stored decimal amount is malformed")
    canonical = text.lstrip("0") or "0"
    if canonical != text:
        raise ExplorerSchemaError("stored decimal amount is not canonical")
    return text


def _validated_batch_size(batch_size: Any) -> int:
    try:
        size = int(batch_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("batch_size must be an integer") from exc
    if not 1 <= size <= 10_000:
        raise ValueError("batch_size must be between 1 and 10000")
    return size


def _validated_page(limit: Any, offset: Any) -> Tuple[int, int]:
    try:
        page_limit = int(limit)
        page_offset = int(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit and offset must be integers") from exc
    if not 1 <= page_limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
    if page_offset < 0:
        raise ValueError("offset must not be negative")
    return page_limit, page_offset


def _block_row(row: sqlite3.Row) -> dict:
    return {
        "height": int(row["height"]),
        "id": row["id"],
        "prev_block_hash": row["prev_block_hash"],
        "miner": row["miner"],
        "timestamp": int(row["timestamp"]),
        "bits": row["bits"],
        "nonce": int(row["nonce"]),
        "version": int(row["version"]),
        "transaction_count": int(row["transaction_count"]),
        "size_bytes": int(row["size_bytes"]),
        "total_fees": _decimal_text(row["total_fees"]),
        "total_transferred": _decimal_text(row["total_transferred"]),
        "reward": _decimal_text(row["reward"]),
    }


def _transaction_row(row: sqlite3.Row, *, indexed_height: int) -> dict:
    block_height = int(row["block_height"])
    return {
        "id": row["id"],
        "block_height": block_height,
        "block_id": row["block_id"],
        "block_timestamp": int(row["block_timestamp"]),
        "transaction_index": int(row["tx_index"]),
        "confirmations": max(0, indexed_height - block_height + 1),
        "chain": int(row["chain_id"]),
        "nonce": int(row["nonce"]),
        "fee": _decimal_text(row["fee"]),
        "value": _decimal_text(row["value"]),
        "from_address": row["from_address"],
        "to_address": row["to_address"],
        "unlock_sig": None,
        "is_coinbase": bool(row["is_coinbase"]),
    }


def _address_row(row: sqlite3.Row) -> dict:
    return {
        "address": row["address"],
        "balance": _decimal_text(row["balance"]),
        "nonce": int(row["nonce"]),
        "total_received": _decimal_text(row["total_received"]),
        "total_sent": _decimal_text(row["total_sent"]),
        "total_fees": _decimal_text(row["total_fees"]),
        "transaction_count": int(row["transaction_count"]),
        "first_seen_height": int(row["first_seen_height"]),
        "last_seen_height": int(row["last_seen_height"]),
    }


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DATABASE_NAME",
    "DEFAULT_POLL_INTERVAL",
    "ExplorerChainDivergence",
    "ExplorerIndex",
    "ExplorerIndexer",
    "ExplorerIndexError",
    "ExplorerIndexNotInitialized",
    "ExplorerNetworkMismatch",
    "ExplorerSchemaError",
    "MAX_PAGE_SIZE",
    "SCHEMA_VERSION",
]
