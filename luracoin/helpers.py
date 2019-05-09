import json
import os
import binascii
import hashlib
from typing import Union
from luracoin.config import Config


def sha256d(s: Union[str, bytes]) -> str:
    """A double SHA-256 hash."""
    if not isinstance(s, bytes):
        s = s.encode()

    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


def little_endian(num_bytes: int, data: int) -> str:
    return data.to_bytes(num_bytes, byteorder="little", signed=False).hex()


def little_endian_to_int(little_endian_bytes: str) -> int:
    return int.from_bytes(
        binascii.unhexlify(little_endian_bytes), byteorder="little"
    )


def var_int(num: int) -> str:
    """
    A VarInt (variable integer) is a field used in serialized data to
    indicate the number of upcoming fields, or the length of an upcoming
    field.
    """
    if num <= 252:
        result = little_endian(num_bytes=1, data=num)
    elif num <= 65535:
        result = "fd" + little_endian(num_bytes=2, data=num)
    elif num <= 4_294_967_295:
        result = "fe" + little_endian(num_bytes=4, data=num)
    else:
        result = "ff" + little_endian(num_bytes=8, data=num)

    return result


def var_int_to_bytes(two_first_bytes: str) -> int:
    if two_first_bytes == "ff":
        return 8
    elif two_first_bytes == "fe":
        return 4
    elif two_first_bytes == "fd":
        return 2
    return 1


def mining_reward() -> int:
    return 50


def is_hex(s: str) -> bool:
    try:
        int(s, 16)
    except ValueError:
        return False
    return len(s) % 2 == 0


def bits_to_target(bits: str) -> str:
    """
    The first byte is the exponent and the other three bytes are the
    coefficient.

    Example:
        0x1d00ffff => 00000000ffff000000000000000000000000...[0x1d = 29 bytes]
    """

    # We get the first two characters which is the first byte and convert it
    # to an integer, later we substract three bytes which are the coefficient
    # and after that we multiply that for two, because each byte has two chars
    target_exponent_number = (int(bits[0:2], 16) - 3) * 2
    target_exponent = "".join(["0" for d in range(target_exponent_number)])

    # The target ahs to be 32 bytes, so 64 characters. We need to add 0's at
    # the start of the target as padding. Also here we need to add 6 because
    # we need to take in account the exponent too
    padding_number = 64 - target_exponent_number - 6
    padding = "".join(["0" for d in range(padding_number)])

    return padding + bits[2:8] + target_exponent


def get_blk_file_size(file_name: str) -> int:
    path = Config.BLOCKS_DIR + file_name
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def block_index_disk_read(serialised_block_index_data: str) -> dict:
    """
    Everytime you have a block into the database the client will save a record
    on LevelDB that will include the basic information, for example, the
    Height, name of the file in which the data is stored, etc...

    It's saved serialised, so in order to read it we need to deserialise it.

    :param serialised_block_index_data: Each index includes:
        The block header.
        The height.
        The number of transactions.
        To what extent this block is validated.
        In which file, and where in that file, the block data is stored.
    """
    block_index = {}
    cursor = 0

    # HEADER
    block_index["header"] = serialised_block_index_data[cursor:164]
    cursor = 164
    total_length_data = len(serialised_block_index_data)

    # HEIGHT
    num_bytes = var_int_to_bytes(
        serialised_block_index_data[cursor : cursor + 2]
    )
    if num_bytes == 1:
        height_serialised = serialised_block_index_data[cursor : cursor + 2]
        height_serialised_len = 2
    else:
        cursor += 2  # The first byte is the control one
        height_serialised = serialised_block_index_data[
            cursor : cursor + (num_bytes * 2)
        ]
        height_serialised_len = num_bytes * 2

    block_index["height"] = little_endian_to_int(height_serialised)
    cursor += height_serialised_len

    # NUMBER OF TRANSACTIONS
    num_bytes = var_int_to_bytes(
        serialised_block_index_data[cursor : cursor + 2]
    )
    if num_bytes == 1:
        num_txns_serialised = serialised_block_index_data[cursor : cursor + 2]
        num_txns_serialised_len = 2
    else:
        cursor += 2  # The first byte is the control one
        num_txns_serialised = serialised_block_index_data[
            cursor : cursor + (num_bytes * 2)
        ]
        num_txns_serialised_len = num_bytes * 2

    block_index["txns"] = little_endian_to_int(num_txns_serialised)
    cursor += num_txns_serialised_len

    # FILE NAME
    file = little_endian_to_int(
        serialised_block_index_data[cursor : cursor + 6]
    )
    block_index["file"] = str(file).zfill(6)
    cursor += 6

    # IS VALIDATED
    is_validated = little_endian_to_int(
        serialised_block_index_data[cursor : cursor + 2]
    )
    block_index["is_validated"] = True if is_validated == 1 else False
    cursor += 2

    assert total_length_data == cursor
    return block_index


def block_index_disk_write(block_index_data: str) -> str:
    # Header
    serialised = block_index_data["header"]

    # Height
    serialised += var_int(block_index_data["height"])

    # Number of transactions
    serialised += var_int(block_index_data["txns"])

    # File name
    serialised += little_endian(
        num_bytes=3, data=int(block_index_data["file"])
    )

    # Is validated
    serialised += little_endian(
        num_bytes=1, data=int(block_index_data["is_validated"])
    )

    return serialised
