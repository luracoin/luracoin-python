"""Block construction, validation, persistence and retrieval.

The bytes hashed by :attr:`Block.id` are consensus data. Do not replace the
canonical byte encoding below with Python string representations: those are
not a stable protocol format.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import redis

from luracoin.chain import Chain, blk_file_format, max_block_size
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError, TransactionNotValid
from luracoin.helpers import (
    bits_to_target,
    calculate_new_bits,
    mining_reward,
    sha256d,
)
from luracoin.transactions import Transaction
from luracoin.wallet import is_valid_address

BLOCK_HEADER_SIZE = 118
_save_lock = threading.RLock()
_block_file_lock = threading.RLock()


class Block(Chain):
    def __init__(
        self,
        version: int = None,
        height: int = None,
        miner: str = None,
        prev_block_hash: str = None,
        bits: bytes = None,
        nonce: int = None,
        timestamp: int = None,
        txns: list = None,
    ) -> None:
        self.height = height
        self.miner = miner
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.txns = txns or []

    def _canonical_hash_bytes(self) -> bytes:
        """Return unambiguous bytes committed to by the block id."""
        transaction_bytes = b"".join(txn.serialize() for txn in self.txns)
        return (
            self.version.to_bytes(4, byteorder="little", signed=False)
            + bytes.fromhex(self.prev_block_hash)
            + self.height.to_bytes(4, byteorder="little", signed=False)
            + self.miner.encode("ascii")
            + self.timestamp.to_bytes(4, byteorder="big", signed=False)
            + self.bits
            + self.nonce.to_bytes(4, byteorder="little", signed=False)
            + len(self.txns).to_bytes(2, byteorder="little", signed=False)
            + transaction_bytes
        )

    @property
    def id(self) -> str:
        """Double-SHA256 of the canonical binary block contents."""
        return sha256d(self._canonical_hash_bytes())

    def header(self) -> Any:
        return {
            "height": self.height,
            "prev_block_hash": self.prev_block_hash,
            "miner": self.miner,
            "id": self.id,
            "nonce": self.nonce,
            "version": self.version,
            "timestamp": self.timestamp,
            "bits": self.bits.hex(),
        }

    def json(self) -> dict:
        block = self.header()
        block["txns"] = [txn.json() for txn in self.txns]
        return block

    def select_transactions(self) -> "Block":
        redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
        )
        transactions = []
        seen_ids = set()
        for key in redis_client.keys():
            if isinstance(key, bytes) and key.startswith(b"nonce:"):
                continue
            if isinstance(key, str) and key.startswith("nonce:"):
                continue
            serialized_tx = redis_client.get(key)
            if not serialized_tx:
                continue
            try:
                txn = Transaction().deserialize(serialized_tx)
            except (TransactionNotValid, UnicodeDecodeError):
                continue
            if txn.id in seen_ids or txn.is_coinbase:
                continue
            seen_ids.add(txn.id)
            transactions.append(txn)

        transactions.sort(
            key=lambda transaction: (-transaction.fee, transaction.id)
        )

        max_size = max_block_size(self.height or 0) - BLOCK_HEADER_SIZE
        selected = []
        current_size = 0
        accounts: Dict[str, dict] = {}

        def account_for(address: str) -> dict:
            if address not in accounts:
                accounts[address] = self._copy_account(
                    self.get_account(address)
                )
            return accounts[address]

        pending = list(transactions)
        while pending and len(selected) < Config.MAX_TX_PER_BLOCK - 1:
            made_progress = False
            for txn in list(pending):
                tx_size = len(txn.serialize())
                if tx_size != Config.TRANSACTION_LENGTH:
                    pending.remove(txn)
                    continue
                sender = account_for(txn.from_address)
                if not txn.validate(account=sender):
                    continue
                if current_size + tx_size > max_size:
                    return self._set_selected_transactions(selected)

                receiver = account_for(txn.to_address)
                if (
                    receiver is not sender
                    and receiver["balance"] + txn.value > 0xFFFFFFFFFFFFFFFF
                ):
                    pending.remove(txn)
                    continue
                sender["balance"] -= txn.value + txn.fee
                sender["nonce"] = txn.nonce
                receiver["balance"] += txn.value
                selected.append(txn)
                current_size += tx_size
                pending.remove(txn)
                made_progress = True
                if len(selected) >= Config.MAX_TX_PER_BLOCK - 1:
                    break
            if not made_progress:
                break

        return self._set_selected_transactions(selected)

    def _set_selected_transactions(self, transactions: list) -> "Block":
        self.txns = transactions
        return self

    def clean_mempool(self) -> None:
        """Remove included transactions from the configured Redis mempool."""
        try:
            redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
            )
            for txn in self.txns:
                if not txn.is_coinbase:
                    redis_client.delete(txn.id, txn.mempool_nonce_key)
        except redis.exceptions.ConnectionError:
            pass

    def serialize(self) -> bytes:
        return (
            self.version.to_bytes(4, byteorder="little", signed=False)
            + bytes.fromhex(self.id)
            + bytes.fromhex(self.prev_block_hash)
            + self.height.to_bytes(4, byteorder="little", signed=False)
            + self.miner.encode("ascii")
            + self.timestamp.to_bytes(4, byteorder="big", signed=False)
            + self.bits
            + self.nonce.to_bytes(4, byteorder="little", signed=False)
            + b"".join(txn.serialize() for txn in self.txns)
        )

    def deserialize(self, block_serialized: bytes) -> "Block":
        if not isinstance(block_serialized, bytes):
            raise BlockNotValidError("A serialized block must be bytes.")
        if len(block_serialized) < BLOCK_HEADER_SIZE:
            raise BlockNotValidError("Truncated block header.")
        payload_size = len(block_serialized) - BLOCK_HEADER_SIZE
        if payload_size % Config.TRANSACTION_LENGTH:
            raise BlockNotValidError(
                "Truncated or non-canonical transaction payload."
            )
        if payload_size // Config.TRANSACTION_LENGTH > Config.MAX_TX_PER_BLOCK:
            raise BlockNotValidError("Block contains too many transactions.")

        declared_id = block_serialized[4:36].hex()
        self.version = int.from_bytes(
            block_serialized[0:4], byteorder="little"
        )
        self.prev_block_hash = block_serialized[36:68].hex()
        self.height = int.from_bytes(
            block_serialized[68:72], byteorder="little"
        )
        try:
            self.miner = block_serialized[72:106].decode("ascii")
        except UnicodeDecodeError as exc:
            raise BlockNotValidError("Miner address is not ASCII.") from exc
        self.timestamp = int.from_bytes(
            block_serialized[106:110], byteorder="big"
        )
        self.bits = block_serialized[110:114]
        self.nonce = int.from_bytes(
            block_serialized[114:118], byteorder="little"
        )
        self.txns = []

        transaction_payload = block_serialized[BLOCK_HEADER_SIZE:]
        for offset in range(
            0, len(transaction_payload), Config.TRANSACTION_LENGTH
        ):
            txn = Transaction()
            txn.deserialize(
                transaction_payload[
                    offset : offset + Config.TRANSACTION_LENGTH
                ]
            )
            self.txns.append(txn)

        if declared_id != self.id:
            raise BlockNotValidError(
                "Serialized block id does not match its contents."
            )
        return self

    def is_valid_proof(self) -> bool:
        try:
            target = int(bits_to_target(self.bits), 16)
            return target > 0 and int(self.id, 16) <= target
        except (AttributeError, OverflowError, TypeError, ValueError):
            return False

    @classmethod
    def expected_bits(cls, height: int) -> bytes:
        """Return the only permitted compact target for ``height``.

        Difficulty derivation is deliberately fail-closed: a node that lacks
        the required history cannot guess a target and accept a block under it.
        """
        if not isinstance(height, int) or not 0 <= height <= 0xFFFFFFFF:
            raise BlockNotValidError(
                "Block height must be a non-negative integer."
            )
        if height == 0:
            return Config.STARTING_DIFFICULTY

        previous = cls.get(height - 1)
        if previous is None:
            raise BlockNotValidError(
                f"Cannot derive difficulty: block {height - 1} is missing."
            )

        interval = Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        if height % interval:
            return previous.bits

        first = cls.get(height - interval)
        if first is None:
            raise BlockNotValidError(
                "Cannot derive difficulty: block "
                f"{height - interval} is missing."
            )
        actual_time = previous.timestamp - first.timestamp
        expected_time = interval * Config.BLOCK_TIME
        return calculate_new_bits(previous.bits, actual_time, expected_time)

    def _validate_fields(self) -> None:
        if self.version != 1:
            raise BlockNotValidError("Unsupported block version.")
        if (
            not isinstance(self.height, int)
            or not 0 <= self.height <= 0xFFFFFFFF
        ):
            raise BlockNotValidError("Invalid block height.")
        if not is_valid_address(self.miner):
            raise BlockNotValidError("Invalid miner address.")
        if (
            not isinstance(self.prev_block_hash, str)
            or len(self.prev_block_hash) != 64
        ):
            raise BlockNotValidError("Invalid previous block hash.")
        try:
            bytes.fromhex(self.prev_block_hash)
        except ValueError as exc:
            raise BlockNotValidError(
                "Previous block hash is not hexadecimal."
            ) from exc
        if (
            not isinstance(self.timestamp, int)
            or not 0 <= self.timestamp <= 0xFFFFFFFF
        ):
            raise BlockNotValidError("Invalid block timestamp.")
        if not isinstance(self.bits, bytes) or len(self.bits) != 4:
            raise BlockNotValidError("Invalid compact difficulty.")
        if (
            not isinstance(self.nonce, int)
            or not 0 <= self.nonce <= 0xFFFFFFFF
        ):
            raise BlockNotValidError("Invalid proof-of-work nonce.")
        if (
            not isinstance(self.txns, list)
            or not 1 <= len(self.txns) <= Config.MAX_TX_PER_BLOCK
        ):
            raise BlockNotValidError("Invalid transaction count.")
        for txn in self.txns:
            if not isinstance(txn, Transaction) or not txn.validate_fields():
                raise BlockNotValidError(
                    "Block contains malformed transaction data."
                )

    def _validate_link_and_difficulty(self) -> None:
        expected_bits = self.expected_bits(self.height)
        if self.bits != expected_bits:
            raise BlockNotValidError("Unexpected difficulty target.")

        if self.height == 0:
            if self.prev_block_hash != "0" * 64:
                raise BlockNotValidError("Genesis previous hash must be zero.")
            from luracoin.genesis import validate_genesis_manifest

            validate_genesis_manifest(self)
            return

        previous = Block.get(self.height - 1)
        if previous is None:
            raise BlockNotValidError("Previous block is missing.")
        if self.prev_block_hash != previous.id:
            raise BlockNotValidError(
                "Previous block hash does not match chain history."
            )
        if self.timestamp <= previous.timestamp:
            raise BlockNotValidError(
                "Block timestamp does not follow its predecessor."
            )

    def _validate_coinbase(self) -> None:
        coinbase_positions = [
            index
            for index, transaction in enumerate(self.txns)
            if transaction.is_coinbase
        ]
        if coinbase_positions != [0]:
            raise BlockNotValidError(
                "A block must have exactly one leading coinbase."
            )

        coinbase = self.txns[0]
        if (
            coinbase.chain != Config.CHAIN_ID
            or coinbase.nonce != self.height
            or coinbase.fee != 0
            or coinbase.from_address != "0" * 34
            or coinbase.to_address != self.miner
        ):
            raise BlockNotValidError("Invalid coinbase fields.")

        if any(
            transaction.chain != Config.CHAIN_ID for transaction in self.txns
        ):
            raise BlockNotValidError("Transaction belongs to another network.")
        transaction_ids = [transaction.id for transaction in self.txns]
        if len(transaction_ids) != len(set(transaction_ids)):
            raise BlockNotValidError(
                "A block cannot contain a transaction twice."
            )

        fees = sum(transaction.fee for transaction in self.txns[1:])
        expected_value = (
            Config.COINS_TO_FORGE
            if self.height == 0
            else mining_reward(self.height) + fees
        )
        if coinbase.value != expected_value:
            raise BlockNotValidError(
                "Coinbase value does not equal subsidy plus fees."
            )

    @staticmethod
    def _copy_account(account: Optional[dict]) -> dict:
        if not account:
            return {"balance": 0, "nonce": 0}
        try:
            balance = int(account["balance"])
            nonce = int(account["nonce"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BlockNotValidError(
                "Stored account state is malformed."
            ) from exc
        if (
            not 0 <= balance <= 0xFFFFFFFFFFFFFFFF
            or not 0 <= nonce <= 0xFFFFFFFF
        ):
            raise BlockNotValidError("Stored account state is malformed.")
        return {"balance": balance, "nonce": nonce}

    def _compute_account_updates(self) -> Dict[str, dict]:
        """Evaluate every transaction against one sequential state snapshot."""
        updates: Dict[str, dict] = {}

        def account_for(address: str) -> dict:
            if address not in updates:
                updates[address] = self._copy_account(
                    self.get_account(address)
                )
            return updates[address]

        # Newly minted value cannot be spent inside the block that creates it.
        for transaction in self.txns[1:]:
            sender = account_for(transaction.from_address)
            if not transaction.validate(account=sender):
                raise BlockNotValidError(
                    "Invalid contextual transaction state."
                )
            debit = transaction.value + transaction.fee
            sender["balance"] -= debit
            sender["nonce"] = transaction.nonce

            receiver = account_for(transaction.to_address)
            receiver["balance"] += transaction.value
            if receiver["balance"] > 0xFFFFFFFFFFFFFFFF:
                raise BlockNotValidError("Account balance overflow.")

        miner = account_for(self.miner)
        miner["balance"] += self.txns[0].value
        if miner["balance"] > 0xFFFFFFFFFFFFFFFF:
            raise BlockNotValidError("Account balance overflow.")
        return updates

    def _validate_or_raise(self, *, check_state: bool) -> None:
        self._validate_fields()
        self._validate_link_and_difficulty()
        self._validate_coinbase()

        serialized_size = len(self.serialize())
        if serialized_size > max_block_size(self.height):
            raise BlockNotValidError("Block exceeds the active size limit.")
        if self.timestamp > int(time.time()) + Config.MAX_FUTURE_BLOCK_TIME:
            raise BlockNotValidError(
                "Block timestamp is too far in the future."
            )
        if not self.is_valid_proof():
            raise BlockNotValidError(
                "Block proof of work does not meet its target."
            )
        if check_state:
            self._compute_account_updates()

    def validate(
        self,
        raise_exception: bool = False,
        *,
        check_state: bool = True,
    ) -> bool:
        try:
            self._validate_or_raise(check_state=check_state)
        except (BlockNotValidError, OverflowError, TypeError, ValueError):
            if raise_exception:
                raise
            return False
        return True

    @classmethod
    def _get_block_records_from_file(cls, file_number: int):
        """Return ``(offset, length, block)`` records from one block file.

        Legacy v2 file-only indexes use this scan once and are then upgraded to
        precise locations. The block-file lock prevents a reader thread from
        treating an append in progress as a truncated persisted record without
        coupling reads to account/index updates or mempool cleanup.
        """
        block_file = (
            Path(Config.BLOCKS_DIR) / f"blk{blk_file_format(file_number)}.dat"
        )
        with _block_file_lock:
            if not block_file.exists():
                return []

            records = []
            with block_file.open("rb") as stream:
                while True:
                    offset = stream.tell()
                    encoded_length = stream.read(4)
                    if not encoded_length:
                        break
                    if len(encoded_length) != 4:
                        raise BlockNotValidError(
                            "Truncated block length prefix."
                        )
                    block_size = int.from_bytes(
                        encoded_length, byteorder="little", signed=False
                    )
                    if (
                        not BLOCK_HEADER_SIZE
                        <= block_size
                        <= Config.MAX_BLOCK_SERIALIZED_SIZE
                    ):
                        raise BlockNotValidError(
                            "Invalid serialized block length."
                        )
                    payload = stream.read(block_size)
                    if len(payload) != block_size:
                        raise BlockNotValidError("Truncated block record.")
                    records.append(
                        (offset, block_size, cls().deserialize(payload))
                    )
            return records

    @classmethod
    def get_blocks_from_file(cls, file_number: int):
        """Read independent blocks from one length-prefixed file."""
        return [
            block
            for _offset, _length, block in cls._get_block_records_from_file(
                file_number
            )
        ]

    @classmethod
    def _read_block_at_location(
        cls, file_number: int, offset: int, expected_length: int
    ) -> "Block":
        """Read and validate exactly one length-prefixed block record."""
        record = cls._read_block_record_at_offset(
            file_number, offset, expected_length=expected_length
        )
        if record is None:
            raise BlockNotValidError("Indexed block record is missing.")
        block_size, block = record
        if block_size != expected_length:
            raise BlockNotValidError(
                "Indexed block length does not match its record."
            )
        return block

    @classmethod
    def _read_block_record_at_offset(
        cls,
        file_number: int,
        offset: int,
        *,
        expected_length: Optional[int] = None,
        require_eof: bool = False,
    ) -> Optional[tuple[int, "Block"]]:
        """Read one record at ``offset``, or ``None`` only at a clean EOF."""
        block_file = (
            Path(Config.BLOCKS_DIR) / f"blk{blk_file_format(file_number)}.dat"
        )
        with _block_file_lock:
            if not block_file.exists():
                return None
            with block_file.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                file_size = stream.tell()
                if offset == file_size:
                    return None
                if offset > file_size:
                    raise BlockNotValidError(
                        "Indexed block offset exceeds its file."
                    )
                stream.seek(offset)
                encoded_length = stream.read(4)
                if len(encoded_length) != 4:
                    raise BlockNotValidError(
                        "Indexed block length prefix is truncated."
                    )
                block_size = int.from_bytes(
                    encoded_length, byteorder="little", signed=False
                )
                if (
                    expected_length is not None
                    and block_size != expected_length
                ):
                    raise BlockNotValidError(
                        "Indexed block length does not match its record."
                    )
                if (
                    not BLOCK_HEADER_SIZE
                    <= block_size
                    <= Config.MAX_BLOCK_SERIALIZED_SIZE
                ):
                    raise BlockNotValidError("Invalid indexed block length.")
                payload = stream.read(block_size)
                if len(payload) != block_size:
                    raise BlockNotValidError(
                        "Indexed block record is truncated."
                    )
                if require_eof and stream.tell() != file_size:
                    raise BlockNotValidError(
                        "Unindexed block record is not the file tail."
                    )
        return block_size, cls().deserialize(payload)

    @classmethod
    def _upgrade_legacy_file_locations(
        cls, chain: Chain, file_number: int, records: list
    ) -> None:
        """Upgrade every legacy entry represented by one scanned v2 file."""
        records_by_height = {}
        for offset, length, block in records:
            if block.height in records_by_height:
                raise BlockNotValidError(
                    "Block file contains duplicate indexed heights."
                )
            records_by_height[block.height] = (offset, length)

        locations = {}
        for height, (offset, length) in records_by_height.items():
            if chain.get_block_location(height) == (
                file_number,
                None,
                None,
            ):
                locations[height] = (file_number, offset, length)
        chain.set_block_locations(locations)

    @classmethod
    def _find_unindexed_next_block(
        cls, height: int, block_id: str
    ) -> Optional[tuple[int, int, int, "Block"]]:
        """Recover a crash-orphaned next block without scanning chain files.

        Saves are serialized, so an append that completed before its index was
        published can only be immediately after the current tip or at offset
        zero of the following file. Any other record at either position is a
        conflicting/corrupt write and must not be silently skipped.
        """
        if height == 0:
            candidates = [(0, 0)]
        else:
            previous = Chain().get_block_location(height - 1)
            if previous is None:
                raise BlockNotValidError("Previous block location is missing.")
            previous_file, previous_offset, previous_length = previous
            if previous_offset is None or previous_length is None:
                # Validation reads the predecessor first and should have
                # upgraded a legacy v2 entry to a precise location.
                raise BlockNotValidError(
                    "Previous block location could not be upgraded."
                )
            candidates = [
                (
                    previous_file,
                    previous_offset + 4 + previous_length,
                ),
                (previous_file + 1, 0),
            ]

        for file_number, offset in candidates:
            record = cls._read_block_record_at_offset(
                file_number, offset, require_eof=True
            )
            if record is None:
                continue
            length, block = record
            if block.height != height or block.id != block_id:
                raise BlockNotValidError(
                    "Unexpected unindexed block record after the chain tip."
                )
            return file_number, offset, length, block
        return None

    @classmethod
    def last(cls):
        chain = cls()
        if chain.get_block_file_number(0) is None:
            return None
        return cls.get(chain.tip)

    @classmethod
    def get(cls, height):
        if not isinstance(height, int) or not 0 <= height <= 0xFFFFFFFF:
            return None
        chain = cls()
        location = chain.get_block_location(height)
        if location is None:
            return None

        file_number, offset, length = location
        if offset is not None and length is not None:
            block = cls._read_block_at_location(file_number, offset, length)
            if block.height != height:
                raise BlockNotValidError(
                    "Indexed block height does not match its record."
                )
            return block

        # Existing v2 alpha directories used a file-only index. Scan that one
        # known file once and replace the entry with a precise location. No v1
        # data or unknown index representation is accepted.
        records = cls._get_block_records_from_file(file_number)
        cls._upgrade_legacy_file_locations(chain, file_number, records)
        for record_offset, record_length, block in records:
            if block.height == height:
                return block
        raise BlockNotValidError(
            "Legacy block index points to a file without that height."
        )

    @classmethod
    def get_many(cls, heights: Iterable[int]) -> Dict[int, "Block"]:
        """Load indexed heights via exact reads or one legacy file scan."""

        requested = {
            height
            for height in heights
            if isinstance(height, int) and 0 <= height <= 0xFFFFFFFF
        }
        if not requested:
            return {}

        chain = cls()
        precise_locations = {}
        legacy_by_file: Dict[int, set] = {}
        for height in requested:
            location = chain.get_block_location(height)
            if location is None:
                continue
            file_number, offset, length = location
            if offset is None or length is None:
                legacy_by_file.setdefault(file_number, set()).add(height)
            else:
                precise_locations[height] = location

        result = {}
        for height, location in precise_locations.items():
            block = cls._read_block_at_location(*location)
            if block.height != height:
                raise BlockNotValidError(
                    "Indexed block height does not match its record."
                )
            result[height] = block

        for file_number, file_heights in legacy_by_file.items():
            records = cls._get_block_records_from_file(file_number)
            cls._upgrade_legacy_file_locations(chain, file_number, records)
            for _offset, _length, block in records:
                if block.height in file_heights and block.height not in result:
                    result[block.height] = block
            missing = file_heights.difference(result)
            if missing:
                raise BlockNotValidError(
                    "Legacy block index points to a file without a requested "
                    "height."
                )
        return result

    @staticmethod
    def _append_record(file_number: int, serialized_block: bytes) -> tuple:
        """Append/fsync one record; return offset and payload size."""
        Config.ensure_data_dirs()
        path = (
            Path(Config.BLOCKS_DIR) / f"blk{blk_file_format(file_number)}.dat"
        )
        record = (
            len(serialized_block).to_bytes(4, byteorder="little")
            + serialized_block
        )
        with _block_file_lock:
            with path.open("ab+") as stream:
                stream.seek(0, os.SEEK_END)
                offset = stream.tell()
                stream.write(record)
                stream.flush()
                os.fsync(stream.fileno())
        return offset, len(serialized_block)

    def save(self) -> None:
        """Persist one valid next block and apply its state transition once."""
        with _save_lock:
            indexed = Block.get(self.height)
            applied_id = self.get_applied_block_id(self.height)
            if indexed is not None:
                if indexed.id != self.id:
                    raise BlockNotValidError(
                        f"Height {self.height} is already occupied by "
                        "another block."
                    )

            if applied_id is not None and applied_id != self.id:
                raise BlockNotValidError(
                    f"Height {self.height} already changed account state."
                )

            genesis_exists = self.get_block_file_number(0) is not None
            expected_height = self.tip + 1 if genesis_exists else 0
            if (
                applied_id is None
                and indexed is None
                and self.height != expected_height
            ):
                raise BlockNotValidError(
                    f"Expected block height {expected_height}, "
                    f"got {self.height}."
                )

            self._validate_or_raise(check_state=applied_id is None)
            updates = (
                self._compute_account_updates() if applied_id is None else None
            )
            serialized_block = self.serialize()

            location = self.get_block_location(self.height)
            if indexed is not None and location is not None:
                file_number, offset, length = location
                persisted = (
                    (file_number, offset, length, indexed)
                    if offset is not None and length is not None
                    else None
                )
            else:
                persisted = self._find_unindexed_next_block(
                    self.height, self.id
                )
            if persisted is None:
                file_number = self.file_number_for_block(len(serialized_block))
                offset, length = self._append_record(
                    file_number, serialized_block
                )
            else:
                file_number, offset, length, recovered = persisted
                if recovered.height != self.height:
                    raise BlockNotValidError(
                        "Block id is persisted at another height."
                    )

            if updates is not None:
                try:
                    self.apply_account_updates(self.height, self.id, updates)
                except ValueError as exc:
                    raise BlockNotValidError(str(exc)) from exc

            self.set_block_location(self.height, file_number, offset, length)
            self.commit_block_metadata(
                height=self.height,
                file_number=file_number,
                block_id=self.id,
                transactions=self.txns,
            )
            self.clean_mempool()

    def create(self) -> "Block":
        """Build, mine and persist the next block for ``self.miner``."""
        from luracoin.genesis import initialize_chain
        from luracoin.pow import proof_of_work

        if not is_valid_address(self.miner):
            raise BlockNotValidError("A valid miner address is required.")
        if self.get_block_file_number(0) is None:
            initialize_chain()
        previous = Block.last()
        if previous is None:
            raise BlockNotValidError("Genesis initialization failed.")

        self.height = previous.height + 1
        self.prev_block_hash = previous.id
        self.version = 1
        self.timestamp = max(int(time.time()), previous.timestamp + 1)
        self.bits = Block.expected_bits(self.height)

        regular_transactions = [
            transaction
            for transaction in self.txns
            if not transaction.is_coinbase
        ]
        total_fees = sum(
            transaction.fee for transaction in regular_transactions
        )
        coinbase = Transaction(
            chain=Config.CHAIN_ID,
            nonce=self.height,
            fee=0,
            value=mining_reward(self.height) + total_fees,
            from_address="0" * 34,
            to_address=self.miner,
            unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
        )
        self.txns = [coinbase] + regular_transactions
        self.nonce = 0
        proof_of_work(self)
        self.save()
        return self
