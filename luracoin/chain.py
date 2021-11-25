import os
import rocksdb
from luracoin.config import Config

# Current height, last block, POS miners,
CHAIN_FILENAME = "chainstate.db"
BLOCK_MAP = "blockmap.db"


def open_database(database_name: str) -> rocksdb.DB:
    db = rocksdb.DB(
        f"{Config.BASE_DIR}/data/{database_name}",
        rocksdb.Options(create_if_missing=True),
    )
    return db


def set_value(database_name: str, key: bytes, value: bytes) -> None:
    db = open_database(database_name)
    db.put(key, value)


def get_value(database_name, key):
    db = open_database(database_name)
    return db.get(key)


"""
def get_current_file_number():
    # Get the current file
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    file_number = db.get(b"l")
    # If there is not a current file we'll start by '000000'
    if file_number is None or file_number == "" or file_number == b"":
        file_number = "000000"
    else:
        file_number.decode("utf-8")

    file_name = get_current_file_name(file_number)
    if get_blk_file_size(file_name) >= Config.MAX_FILE_SIZE:
        file_number = next_blk_file(file_number)

    db.close()

    return file_number

def get_current_blk_file() -> str:
    number = get_current_file_number()
    return get_current_file_name(number)
"""


def next_blk_file(current_blk_file: str) -> str:
    """
    Increases by one the blk file name, for example:
    blk000132.dat => blk000133.dat
    :param current_blk_file: <String> Actual file (eg. 000001)
    :return: <String> Next file (eg. 000002)
    """
    return str(int(current_blk_file) + 1).zfill(6)
