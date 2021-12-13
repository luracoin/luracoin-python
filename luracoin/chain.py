import json
import os
import rocksdb
from luracoin.config import Config
from luracoin.helpers import mining_reward
import safer


class Chain(object):
    @property
    def tip(self):
        """
        Return the current height of the chain, the tip of the chain
        """
        current_height = get_value(
            database_name=Config.DATABASE_CHAINSTATE.encode(),
            key="height".encode(),
        )
        if not current_height:
            return 0

        return int.from_bytes(current_height, byteorder="little", signed=False)

    def set_tip(self, height):
        """
        Set the current height, the tip of the chain
        """
        set_value(
            database_name=Config.DATABASE_CHAINSTATE.encode(),
            key="height".encode(),
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
        if get_blk_file_size(file_name) >= Config.MAX_FILE_SIZE:
            file_number += 1

        return file_number

    def set_current_file_number(self, file_number):
        """
        Set the current file number
        """
        set_value(
            database_name=Config.DATABASE_CHAINSTATE,
            key=b"file_number",
            value=file_number.to_bytes(4, byteorder="little", signed=False),
        )

    def get_block_file_number(self, height):
        """
        Get the file number for a block height
        """
        file_number = get_value(
            database_name=Config.DATABASE_BLOCKS,
            key=height.to_bytes(4, byteorder="little", signed=False),
        )

        if not file_number:
            return None

        return int.from_bytes(file_number, byteorder="little", signed=False)

    def set_block_file_number(self, height, file_number):
        """
        Set the file number for a block height
        """
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



def open_database(database_name: str) -> rocksdb.DB:
    """
    Open a RockDB database
    """
    db = rocksdb.DB(
        f"{Config.DATA_DIR}{database_name}",
        rocksdb.Options(create_if_missing=True),
    )
    return db


def set_value(database_name: str, key: bytes, value: bytes) -> None:
    """
    Sets a value in a RocksDB database
    """
    db = open_database(database_name)
    db.put(key, value)


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
    return Config.MAX_BLOCK_SIZE


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
