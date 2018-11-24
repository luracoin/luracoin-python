import binascii
import hashlib
from typing import Union


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
