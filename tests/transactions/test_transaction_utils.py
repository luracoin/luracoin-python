import struct
from unittest.mock import MagicMock
from binascii import unhexlify
from luracoin.transactions import (
    build_script_sig,
    is_valid_unlocking_script,
)
from tests.constants import WALLET_1, WALLET_2


def test_build_script_sig():
    sig = "aabbccdd"
    pubkey = "11223344"
    result = build_script_sig(sig, pubkey)
    assert result == "aabbccdd11223344"


def test_is_valid_unlocking_script_rejects_bad_hex():
    """Passing bytes that produce invalid hex in deserialization should return False."""
    # Create 128 bytes of 0xff which when hex-decoded will be all f's
    # The public key portion will be "ff" * 64 which is not a valid EC point
    bad_sig = b"\xff" * 128

    result = is_valid_unlocking_script(
        unlocking_script=bad_sig,
        transaction_serialized="deadbeef",
        from_address=WALLET_1["address"],
    )
    assert result is False


def test_is_valid_unlocking_script_rejects_malformed_point():
    """Public key that is not a valid EC point should return False."""
    # 128 bytes: first 64 = "public key" (all zeros, not a valid point),
    # next 64 = "signature"
    malformed_sig = b"\x00" * 128

    result = is_valid_unlocking_script(
        unlocking_script=malformed_sig,
        transaction_serialized="deadbeef",
        from_address=WALLET_1["address"],
    )
    assert result is False
