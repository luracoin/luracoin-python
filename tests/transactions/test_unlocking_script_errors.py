import binascii
from unittest.mock import patch, MagicMock
from luracoin.transactions import is_valid_unlocking_script, build_message
from luracoin.helpers import sha256d
from tests.constants import WALLET_1


def test_is_valid_unlocking_script_catches_binascii_error():
    """binascii.Error during deserialization returns False."""
    with patch(
        "luracoin.transactions.deserialize_unlocking_script",
        side_effect=binascii.Error("bad hex"),
    ):
        result = is_valid_unlocking_script(
            unlocking_script=b"\x00" * 128,
            transaction_serialized="deadbeef",
            from_address=WALLET_1["address"],
        )
    assert result is False


def test_is_valid_unlocking_script_catches_assertion_error():
    """AssertionError during signature verification returns False."""
    with patch(
        "luracoin.transactions.deserialize_unlocking_script",
        return_value={
            "signature": "ab" * 32,
            "public_key": "cd" * 32,
            "address": WALLET_1["address"],
        },
    ), patch(
        "luracoin.transactions.ecdsa.VerifyingKey.from_string",
    ) as mock_vk_cls:
        mock_vk = MagicMock()
        mock_vk.to_string.return_value = b"\x03" + b"\x00" * 32
        mock_vk_cls.return_value = mock_vk

        with patch(
            "luracoin.transactions.pubkey_to_address",
            return_value=WALLET_1["address"],
        ), patch(
            "luracoin.transactions.verify_signature",
            side_effect=AssertionError("bad sig"),
        ):
            result = is_valid_unlocking_script(
                unlocking_script=b"\x00" * 128,
                transaction_serialized="deadbeef",
                from_address=WALLET_1["address"],
            )
    assert result is False


def test_build_message():
    """build_message should hash txid + txout_idx + pubkey."""
    outpoint = MagicMock()
    outpoint.txid = "abc123"
    outpoint.txout_idx = 0

    result = build_message(outpoint, "mypubkey")
    expected = sha256d("abc123" + "0" + "mypubkey")
    assert result == expected
