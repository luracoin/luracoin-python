import os
import ecdsa
import binascii
import hashlib
from typing import Union
from luracoin.config import Config


def bits_to_target(bits: bytes) -> hex:
    """
    The first byte is the exponent and the other three bytes are the
    coefficient.
    Example:
        0x1d00ffff => 00000000ffff000000000000000000000000...[0x1d = 29 bytes]
    """

    bits = bits.hex()

    # We get the first two characters which is the first byte and convert it
    # to an integer, later we substract three bytes which are the coefficient
    # and after that we multiply that for two, because each byte has two chars
    target_exponent_number = (int(bits[0:2], 16) - 3) * 2
    target_exponent = "".join(["0" for d in range(target_exponent_number)])

    # The target has to be 32 bytes, so 64 characters. We need to add 0's at
    # the start of the target as padding. Also here we need to add 6 because
    # we need to take in account the exponent too
    padding_number = 64 - target_exponent_number - 6
    padding = "".join(["0" for d in range(padding_number)])

    return padding + bits[2:8] + target_exponent


def sha256d(s: Union[str, bytes]) -> str:
    """A double SHA-256 hash."""
    if not isinstance(s, bytes):
        s = s.encode()

    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


def mining_reward(height) -> int:
    halving = int(height / Config.HALVING_BLOCKS) + 1
    return int(Config.BLOCK_REWARD / halving)


def little_endian_to_int(little_endian_hex: str) -> int:
    return int.from_bytes(
        binascii.unhexlify(little_endian_hex), byteorder="little"
    )


def is_hex(s: str) -> bool:
    try:
        int(s, 16)
    except ValueError:
        return False
    return len(s) % 2 == 0


def bytes_to_signing_key(private_key: bytes) -> ecdsa.SigningKey:
    return ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)


def calculate_new_bits(prev_bits: bytes, actual_time: int, expected_time: int) -> bytes:
    """
    Adjust difficulty based on actual vs expected time for the last interval.
    Returns new 4-byte compact bits value.
    """
    target = int(bits_to_target(prev_bits), 16)

    # Clamp adjustment to 4x in either direction
    if actual_time < expected_time // 4:
        actual_time = expected_time // 4
    if actual_time > expected_time * 4:
        actual_time = expected_time * 4

    new_target = target * actual_time // expected_time

    # Cap at maximum target
    max_target = int(bits_to_target(b"\x1f\xff\xff\xff"), 16)
    if new_target > max_target:
        new_target = max_target

    # Convert target integer back to compact bits format
    # Express new_target as: coefficient * 256^(exponent-3)
    if new_target == 0:
        return b"\x00\x00\x00\x00"

    # Get byte representation of target
    target_bytes = new_target.to_bytes((new_target.bit_length() + 7) // 8, byteorder="big")
    exponent = len(target_bytes)

    # Coefficient is the top 3 bytes
    if exponent >= 3:
        coefficient = target_bytes[:3]
    else:
        coefficient = target_bytes.ljust(3, b"\x00")

    return bytes([exponent]) + coefficient
