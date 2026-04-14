import pytest
from binascii import unhexlify
from unittest.mock import patch, MagicMock
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.exceptions import TransactionNotValid
from luracoin import errors
from tests.constants import WALLET_1, WALLET_2


# ---------------------------------------------------------------------------
# make_msg()
# ---------------------------------------------------------------------------

def test_make_msg_returns_transaction_id():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.make_msg() == tx.id


# ---------------------------------------------------------------------------
# validate() raise_exception paths for balance/nonce
# ---------------------------------------------------------------------------

def test_validate_no_account_raises():
    """validate(raise_exception=True) raises for sender with no account."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_NO_BALANCE):
        tx.validate(raise_exception=True)


def test_validate_insufficient_balance_raises():
    """validate(raise_exception=True) raises for insufficient balance."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 500, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_NO_BALANCE):
        tx.validate(raise_exception=True)


def test_validate_invalid_nonce_raises():
    """validate(raise_exception=True) raises for wrong nonce."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 5})

    tx = Transaction(
        chain=1, nonce=3, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_INVALID_NONCE):
        tx.validate(raise_exception=True)


def test_validate_invalid_signature_raises():
    """validate(raise_exception=True) raises for mismatched signature."""
    chain = Chain()
    chain.set_account(WALLET_2["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )
    # Sign with wrong key
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_INVALID_SIGNATURE):
        tx.validate(raise_exception=True)


# ---------------------------------------------------------------------------
# validate_fields() raise_exception for from_address
# ---------------------------------------------------------------------------

def test_validate_fields_missing_from_address_raises():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_FIELD_FROM_ADDRESS):
        tx.validate_fields(raise_exception=True)


def test_validate_fields_short_from_address_raises():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address="too_short",
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    with pytest.raises(TransactionNotValid, match=errors.TRANSACTION_FIELD_FROM_ADDRESS):
        tx.validate_fields(raise_exception=True)


# ---------------------------------------------------------------------------
# to_transaction_pool() success path
# ---------------------------------------------------------------------------

def test_to_transaction_pool_accepts_valid_tx():
    """Valid transaction should be accepted into the mempool."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    mock_redis = MagicMock()
    with patch("luracoin.transactions.redis.Redis", return_value=mock_redis):
        result = tx.to_transaction_pool()

    assert result is True
    mock_redis.set.assert_called_once_with(tx.id, tx.serialize())


# ---------------------------------------------------------------------------
# Transaction.json() with None unlock_sig
# ---------------------------------------------------------------------------

def test_json_with_no_unlock_sig():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    j = tx.json()
    assert j["unlock_sig"] is None
    assert j["chain"] == 1
    assert j["value"] == 5_000


# ---------------------------------------------------------------------------
# Transaction.serialize() without unlock_sig
# ---------------------------------------------------------------------------

def test_serialize_without_sig_equals_to_sign():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    # Without unlock_sig set, serialize() and serialize(to_sign=True) should match
    assert tx.serialize() == tx.serialize(to_sign=True)
