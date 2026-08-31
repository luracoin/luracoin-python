import binascii
import hashlib
from typing import Union

from coincurve import PrivateKey

from luracoin.config import Config


def bits_to_target(bits: bytes) -> str:
    """
    The first byte is the exponent and the other three bytes are the
    coefficient.
    Example:
        0x1d00ffff => 00000000ffff000000000000000000000000...[0x1d = 29 bytes]
    """

    if not isinstance(bits, bytes) or len(bits) != 4:
        raise ValueError("compact target must contain exactly four bytes")
    exponent = bits[0]
    coefficient = int.from_bytes(bits[1:], byteorder="big")
    if exponent <= 3:
        target = coefficient >> (8 * (3 - exponent))
    else:
        target = coefficient << (8 * (exponent - 3))
    if target >= 1 << 256:
        raise ValueError("compact target exceeds 256 bits")
    return f"{target:064x}"


def sha256d(s: Union[str, bytes]) -> str:
    """A double SHA-256 hash."""
    data = s if isinstance(s, bytes) else s.encode()
    return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()


def mining_reward(height: int) -> int:
    """Return the block subsidy after true halvings and tail-emission floor."""
    if not isinstance(height, int) or height < 0:
        raise ValueError("height must be a non-negative integer")
    era = height // Config.HALVING_BLOCKS
    subsidy = Config.BLOCK_REWARD >> era
    return max(subsidy, Config.TAIL_REWARD)


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


def bytes_to_signing_key(private_key: bytes) -> PrivateKey:
    """Return a libsecp256k1 private key from its canonical 32 bytes."""
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise ValueError("Private key must contain exactly 32 bytes.")
    return PrivateKey(private_key)


def calculate_new_bits(
    prev_bits: bytes, actual_time: int, expected_time: int
) -> bytes:
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
    target_bytes = new_target.to_bytes(
        (new_target.bit_length() + 7) // 8, byteorder="big"
    )
    exponent = len(target_bytes)

    # Coefficient is the top 3 bytes
    if exponent >= 3:
        coefficient = target_bytes[:3]
    else:
        coefficient = target_bytes.ljust(3, b"\x00")

    return bytes([exponent]) + coefficient
