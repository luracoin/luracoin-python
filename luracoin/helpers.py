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
