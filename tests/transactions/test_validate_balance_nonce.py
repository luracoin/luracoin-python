import pytest
from binascii import unhexlify
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.exceptions import TransactionNotValid
from luracoin import errors
from tests.constants import WALLET_1, WALLET_2


# ---------------------------------------------------------------------------
# 2.3 - Balance validation
# ---------------------------------------------------------------------------

def test_validate_rejects_insufficient_balance():
    """Sender must have balance >= value + fee."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 1_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=2_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is False


def test_validate_rejects_insufficient_balance_raises():
    """raise_exception=True raises TransactionNotValid with correct message."""
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


def test_validate_accepts_exact_balance():
    """Sender with balance == value + fee should pass."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 5_100, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is True


def test_validate_rejects_no_account():
    """Sender with no account at all should fail."""
    chain = Chain()
    # Don't create any account for WALLET_1

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is False


def test_validate_coinbase_skips_balance_check():
    """Coinbase transactions don't need a sender balance."""
    chain = Chain()
    # No account for "0" * 34, and that's fine

    tx = Transaction(
        chain=1, nonce=0, fee=0, value=5_000_000_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert tx.validate() is True


# ---------------------------------------------------------------------------
# 2.4 - Nonce replay protection
# ---------------------------------------------------------------------------

def test_validate_rejects_wrong_nonce():
    """tx.nonce must be account.nonce + 1."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 5})

    # nonce=5 is wrong, should be 6
    tx = Transaction(
        chain=1, nonce=5, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is False


def test_validate_rejects_skipped_nonce():
    """tx.nonce=7 when account.nonce=5 should fail (can't skip)."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 5})

    tx = Transaction(
        chain=1, nonce=7, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is False


def test_validate_accepts_correct_nonce():
    """tx.nonce = account.nonce + 1 should pass."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 5})

    tx = Transaction(
        chain=1, nonce=6, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is True


def test_validate_first_tx_nonce_is_one():
    """First transaction from a new account should have nonce=1 (account.nonce=0)."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is True


def test_validate_coinbase_skips_nonce_check():
    """Coinbase transactions don't check nonce."""
    tx = Transaction(
        chain=1, nonce=0, fee=0, value=5_000_000_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert tx.validate() is True
