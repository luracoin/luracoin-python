import pytest
from unittest.mock import patch
from luracoin.wallet import pubkey_to_address


def test_pubkey_to_address_raises_if_ripemd160_missing():
    """Should raise RuntimeError if ripemd160 is not available."""
    with patch("luracoin.wallet.hashlib") as mock_hashlib:
        mock_hashlib.algorithms_available = {"sha256", "md5"}
        with pytest.raises(RuntimeError, match="missing ripemd160"):
            pubkey_to_address(b"\x03" + b"\x00" * 32)


def test_pubkey_to_address_raises_if_address_not_34_chars():
    """Should raise RuntimeError if generated address is not 34 chars."""
    with patch("luracoin.wallet.b58encode_check", return_value=b"short"):
        with patch("luracoin.wallet.hashlib") as mock_hashlib:
            mock_hashlib.algorithms_available = {"sha256", "ripemd160"}
            mock_hashlib.sha256.return_value.digest.return_value = b"\x00" * 32
            mock_hashlib.new.return_value.digest.return_value = b"\x00" * 20
            with pytest.raises(RuntimeError, match="Invalid address"):
                pubkey_to_address(b"\x03" + b"\x00" * 32)
