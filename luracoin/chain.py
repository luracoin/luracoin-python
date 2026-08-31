import json
import os
import threading

from rocksdict import Rdict, WriteBatch

from luracoin.config import Config

_BLOCK_LOCATION_VERSION = 1
_BLOCK_LOCATION_SIZE = 17


def _encode_block_location(
    file_number: int, offset: int, length: int
) -> bytes:
    if not isinstance(file_number, int) or not 0 <= file_number <= 0xFFFFFFFF:
        raise ValueError("block file number must fit in uint32")
    if not isinstance(offset, int) or not 0 <= offset <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("block offset must fit in uint64")
    if (
        not isinstance(length, int)
        or not 118 <= length <= Config.MAX_BLOCK_SERIALIZED_SIZE
    ):
        raise ValueError("block length is outside configured limits")
    if offset > 0xFFFFFFFFFFFFFFFF - length - 4:
        raise ValueError("block location exceeds uint64")
    return (
        bytes([_BLOCK_LOCATION_VERSION])
        + file_number.to_bytes(4, byteorder="little", signed=False)
        + offset.to_bytes(8, byteorder="little", signed=False)
        + length.to_bytes(4, byteorder="little", signed=False)
    )


class Chain(object):
    @property
    def tip(self):
        """
        Return the current height of the chain, the tip of the chain
        """
        current_height = get_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"height",
        )
        if not current_height:
            return 0

        return int.from_bytes(current_height, byteorder="little", signed=False)

    def set_tip(self, height):
        """
        Set the current height, the tip of the chain
        """
        set_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"height",
            value=height.to_bytes(4, byteorder="little", signed=False),
        )

    @property
    def current_file_number(self):
        """
        Returns the current file number in which we are writing blocks
        """
        file_number = get_value(
            database_name=Config.DATABASE_CHAINSTATE, key=b"file_number"
        )

        # If there is not a current file we'll start by 0
        if file_number is None or file_number == "" or file_number == b"":
            file_number = 0
        else:
            file_number = int.from_bytes(
                file_number, byteorder="little", signed=False
            )

        file_name = get_current_file_name(blk_file_format(file_number))
        while get_blk_file_size(file_name) >= Config.MAX_FILE_SIZE:
            file_number += 1
            file_name = get_current_file_name(blk_file_format(file_number))

        return file_number

    def file_number_for_block(self, serialized_size: int) -> int:
        """Return a file number that can hold a length-prefixed block."""
        file_number = self.current_file_number
        record_size = serialized_size + 4

        while True:
            file_name = get_current_file_name(blk_file_format(file_number))
            file_size = get_blk_file_size(file_name)
            if (
                file_size == 0
                or file_size + record_size <= Config.MAX_FILE_SIZE
            ):
                return file_number
            file_number += 1

    def set_current_file_number(self, file_number):
        """
        Set the current file number
        """
        set_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"file_number",
            value=file_number.to_bytes(4, byteorder="little", signed=False),
        )

    def get_block_location(self, height):
        """Return ``(file_number, offset, length)`` for an indexed height.

        Protocol-v2 alpha directories initially stored only a four-byte file
        number. Those entries remain readable and are returned with ``None``
        for offset and length so block readers can upgrade them lazily. New
        entries are explicitly versioned and malformed/unknown values fail
        closed instead of being interpreted as a different integer layout.
        """
        if not isinstance(height, int) or not 0 <= height <= 0xFFFFFFFF:
            return None
        encoded = get_value(
            database_name=Config.DATABASE_BLOCKS,
            key=height.to_bytes(4, byteorder="little", signed=False),
        )
        if encoded is None:
            return None

        if len(encoded) == 4:
            return (
                int.from_bytes(encoded, byteorder="little", signed=False),
                None,
                None,
            )
        if (
            len(encoded) != _BLOCK_LOCATION_SIZE
            or encoded[0] != _BLOCK_LOCATION_VERSION
        ):
            raise ValueError("Corrupt or unsupported block location index.")

        file_number = int.from_bytes(encoded[1:5], "little", signed=False)
        offset = int.from_bytes(encoded[5:13], "little", signed=False)
        length = int.from_bytes(encoded[13:17], "little", signed=False)
        if not 118 <= length <= Config.MAX_BLOCK_SERIALIZED_SIZE:
            raise ValueError("Corrupt or unsupported block location index.")
        if offset > 0xFFFFFFFFFFFFFFFF - length - 4:
            raise ValueError("Corrupt or unsupported block location index.")
        return file_number, offset, length

    def get_block_file_number(self, height):
        """Return the indexed block file number for ``height``."""
        location = self.get_block_location(height)
        return location[0] if location is not None else None

    def set_block_location(self, height, file_number, offset, length):
        """Persist a versioned, bounded location for one block record."""
        self.set_block_locations({height: (file_number, offset, length)})

    def set_block_locations(self, locations: dict) -> None:
        """Atomically persist several versioned block locations."""
        values = {}
        for height, location in locations.items():
            if not isinstance(height, int) or not 0 <= height <= 0xFFFFFFFF:
                raise ValueError("block height must fit in uint32")
            try:
                file_number, offset, length = location
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid block location") from exc
            values[height.to_bytes(4, byteorder="little", signed=False)] = (
                _encode_block_location(file_number, offset, length)
            )
        if values:
            set_values(Config.DATABASE_BLOCKS, values)

    def get_block_height(self, block_id: str):
        """Return the indexed height for a canonical block id, if known."""

        if not isinstance(block_id, str) or len(block_id) != 64:
            return None
        try:
            block_hash = bytes.fromhex(block_id)
        except ValueError:
            return None
        height = get_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"b" + block_hash,
        )
        if height is None or len(height) != 4:
            return None
        return int.from_bytes(height, byteorder="little", signed=False)

    def get_transaction_location(self, transaction_id: str):
        """Return ``(height, index)`` for a canonical transaction id."""

        if not isinstance(transaction_id, str) or len(transaction_id) != 64:
            return None
        try:
            bytes.fromhex(transaction_id)
        except ValueError:
            return None
        location = get_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"t" + transaction_id.lower().encode(),
        )
        if location is None or len(location) != 6:
            return None
        return (
            int.from_bytes(location[:4], byteorder="little", signed=False),
            int.from_bytes(location[4:], byteorder="little", signed=False),
        )

    def set_block_file_number(self, height, file_number):
        """Write the legacy v2 file-only index representation.

        Retained for compatibility with existing v2 alpha directories and
        callers. New block persistence must use :meth:`set_block_location`.
        """
        if not isinstance(height, int) or not 0 <= height <= 0xFFFFFFFF:
            raise ValueError("block height must fit in uint32")
        if (
            not isinstance(file_number, int)
            or not 0 <= file_number <= 0xFFFFFFFF
        ):
            raise ValueError("block file number must fit in uint32")
        set_value(
            database_name=Config.DATABASE_BLOCKS,
            key=height.to_bytes(4, byteorder="little", signed=False),
            value=file_number.to_bytes(4, byteorder="little", signed=False),
        )

    def get_account(self, address):
        """
        Get the account for a given address
        """
        account = get_value(
            database_name=Config.DATABASE_ACCOUNTS, key=address.encode()
        )

        if not account:
            return None

        return json.loads(account.decode())

    def set_account(self, address, data):
        """
        Set the account for a given address
        """
        set_value(
            database_name=Config.DATABASE_ACCOUNTS,
            key=address.encode(),
            value=json.dumps(data).encode(),
        )

    def credit_account(self, address, amount):
        account = self.get_account(address) or {"balance": 0, "nonce": 0}
        account["balance"] += amount
        self.set_account(address, account)

    def debit_account(self, address, amount):
        account = self.get_account(address) or {"balance": 0, "nonce": 0}
        account["balance"] -= amount
        self.set_account(address, account)

    def increment_nonce(self, address, nonce):
        account = self.get_account(address) or {"balance": 0, "nonce": 0}
        account["nonce"] = nonce
        self.set_account(address, account)

    def get_applied_block_id(self, height: int):
        """Return the state-transition marker for ``height``, if present."""
        value = get_value(
            database_name=Config.DATABASE_ACCOUNTS,
            key=_applied_block_key(height),
        )
        return value.decode() if value else None

    def apply_account_updates(
        self, height: int, block_id: str, accounts: dict
    ) -> bool:
        """Atomically apply all account changes for one block.

        The marker is stored in the same RocksDB batch as the balances. This
        makes retrying ``Block.save`` idempotent even when a process exits
        between the account update and the block/index writes.
        """
        marker_key = _applied_block_key(height)
        existing = get_value(Config.DATABASE_ACCOUNTS, marker_key)
        if existing:
            if existing.decode() != block_id:
                raise ValueError(
                    f"height {height} already applied as {existing.decode()}"
                )
            return False

        values = {
            address.encode(): json.dumps(data, sort_keys=True).encode()
            for address, data in accounts.items()
        }
        values[marker_key] = block_id.encode()
        set_values(Config.DATABASE_ACCOUNTS, values)
        return True

    def commit_block_metadata(
        self,
        *,
        height: int,
        file_number: int,
        block_id: str,
        transactions: list,
    ) -> None:
        """Atomically publish chainstate metadata for a persisted block."""
        values = {
            b"height": height.to_bytes(4, byteorder="little", signed=False),
            b"file_number": file_number.to_bytes(
                4, byteorder="little", signed=False
            ),
            b"b"
            + bytes.fromhex(block_id): height.to_bytes(
                4, byteorder="little", signed=False
            ),
        }

        for index, transaction in enumerate(transactions):
            values[b"t" + transaction.id.encode()] = height.to_bytes(
                4, byteorder="little", signed=False
            ) + index.to_bytes(2, byteorder="little", signed=False)
            for address in {
                transaction.from_address,
                transaction.to_address,
            }:
                if address == "0" * 34:
                    continue
                values[_address_transaction_key(address, height, index)] = (
                    transaction.id.encode()
                )

        set_values(Config.DATABASE_CHAINSTATE, values)

    def get_address_transaction_refs(
        self,
        address: str,
        *,
        limit: int = 50,
        cursor: str = None,
    ) -> tuple:
        """Return newest indexed transaction locations for one address.

        ``cursor`` is the opaque 12-character hex suffix returned by a prior
        call. The per-address RocksDB index avoids rescanning every historical
        block for each wallet refresh.
        """
        if not isinstance(address, str) or len(address) != 34:
            raise ValueError("address must contain exactly 34 characters")
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")

        cursor_bytes = None
        if cursor is not None:
            try:
                cursor_bytes = bytes.fromhex(cursor)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid transaction cursor") from exc
            if len(cursor_bytes) != 6:
                raise ValueError("invalid transaction cursor")

        prefix = _address_transaction_prefix(address)
        iterator = open_database(Config.DATABASE_CHAINSTATE).iter()
        iterator.seek_for_prev(prefix + (cursor_bytes or b"\xff" * 6))
        if (
            cursor_bytes is not None
            and iterator.valid()
            and iterator.key() == prefix + cursor_bytes
        ):
            iterator.prev()

        references = []
        # Read one extra valid entry so ``next_cursor`` means that another
        # page really exists, rather than merely that this page is full.
        while iterator.valid() and len(references) <= limit:
            key = iterator.key()
            if not isinstance(key, bytes) or not key.startswith(prefix):
                break
            suffix = key[len(prefix) :]
            if len(suffix) != 6:
                iterator.prev()
                continue
            raw_id = iterator.value()
            try:
                transaction_id = raw_id.decode()
                bytes.fromhex(transaction_id)
            except (AttributeError, UnicodeDecodeError, ValueError):
                iterator.prev()
                continue
            if len(transaction_id) != 64:
                iterator.prev()
                continue
            references.append(
                {
                    "height": int.from_bytes(suffix[:4], "big"),
                    "index": int.from_bytes(suffix[4:], "big"),
                    "transaction_id": transaction_id,
                    "cursor": suffix.hex(),
                }
            )
            iterator.prev()

        has_more = len(references) > limit
        references = references[:limit]
        next_cursor = references[-1]["cursor"] if has_more else None
        return references, next_cursor


_db_instances = {}
_db_lock = threading.RLock()


def _applied_block_key(height: int) -> bytes:
    return b"\x00applied-block:" + height.to_bytes(
        4, byteorder="little", signed=False
    )


def _address_transaction_prefix(address: str) -> bytes:
    return b"\x00address-tx:" + address.encode()


def _address_transaction_key(address: str, height: int, index: int) -> bytes:
    return (
        _address_transaction_prefix(address)
        + height.to_bytes(4, byteorder="big", signed=False)
        + index.to_bytes(2, byteorder="big", signed=False)
    )


def open_database(database_name: str) -> Rdict:
    """
    Open a RocksDB database (singleton per path).
    """
    Config.ensure_data_dirs()
    path = f"{Config.DATA_DIR}{database_name}"
    with _db_lock:
        if path not in _db_instances:
            _db_instances[path] = Rdict(path)
        return _db_instances[path]


def close_databases():
    """Close all open database connections."""
    with _db_lock:
        for path in list(_db_instances.keys()):
            try:
                _db_instances[path].close()
            except Exception:
                pass
        _db_instances.clear()


def set_value(database_name: str, key: bytes, value: bytes) -> None:
    """
    Sets a value in a RocksDB database
    """
    db = open_database(database_name)
    db[key] = value


def set_values(database_name: str, values: dict) -> None:
    """Write several byte key/value pairs in one RocksDB batch."""
    db = open_database(database_name)
    batch = WriteBatch()
    for key, value in values.items():
        batch[key] = value
    db.write(batch)


def get_value(database_name, key):
    """
    Gets a value from a RocksDB database
    """
    db = open_database(database_name)
    return db.get(key)


def get_blk_file_size(file_name: str) -> int:
    """
    Returns the size of a block file
    """
    path = Config.BLOCKS_DIR + file_name
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def max_block_size(current_height: int) -> int:
    result = Config.MAX_BLOCK_SIZE[0]
    for threshold, size in sorted(Config.MAX_BLOCK_SIZE.items()):
        if current_height >= threshold:
            result = size
        else:
            break
    return result


def get_current_blk_file(current_file_number) -> str:
    """
    Returns the current blk file name with file format.
    """
    return get_current_file_name(blk_file_format(current_file_number))


def get_current_file_name(file_number: str) -> str:
    """ """
    return f"blk{file_number}.dat"


def next_blk_file(current_blk_file: str) -> str:
    """
    Increases by one the blk file name, for example:
    blk000132.dat => blk000133.dat
    :param current_blk_file: <String> Actual file (eg. 000001)
    :return: <String> Next file (eg. 000002)
    """
    return blk_file_format(int(current_blk_file) + 1)


def blk_file_format(number: int) -> str:
    """
    Increases by one the blk file name, for example:
    blk000132.dat => blk000133.dat
    :param current_blk_file: <String> Actual file (eg. 000001)
    :return: <String> Next file (eg. 000002)
    """
    return str(number).zfill(6)
