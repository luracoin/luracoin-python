from binascii import unhexlify
from luracoin.transactions import Transaction
from luracoin.chain import Chain
from tests.constants import WALLET_1, WALLET_2, WALLET_3


def test_double_spend_rejected_by_nonce():
    """Two transactions with the same nonce from the same sender: second fails validation."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx1 = Transaction(
        chain=1, nonce=1, fee=100, value=3_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx1 = tx1.sign(unhexlify(WALLET_1["private_key"]))
    assert tx1.validate() is True
    tx1.save(block_height=1, tx_index=0)

    # Same nonce=1 again
    tx2 = Transaction(
        chain=1, nonce=1, fee=100, value=3_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    )
    tx2 = tx2.sign(unhexlify(WALLET_1["private_key"]))
    assert tx2.validate() is False  # nonce 1 already used, account.nonce is now 1


def test_double_spend_rejected_by_balance():
    """Two transactions that together exceed balance: second fails."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 5_000_000, "nonce": 0})

    tx1 = Transaction(
        chain=1, nonce=1, fee=0, value=3_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx1 = tx1.sign(unhexlify(WALLET_1["private_key"]))
    assert tx1.validate() is True
    tx1.save(block_height=1, tx_index=0)

    # After tx1: balance = 5M - 3M = 2M. Try to spend 3M again.
    tx2 = Transaction(
        chain=1, nonce=2, fee=0, value=3_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    )
    tx2 = tx2.sign(unhexlify(WALLET_1["private_key"]))
    assert tx2.validate() is False  # insufficient balance


def test_sequential_transactions_work():
    """Two valid sequential transactions with correct nonces should both pass."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx1 = Transaction(
        chain=1, nonce=1, fee=100, value=2_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx1 = tx1.sign(unhexlify(WALLET_1["private_key"]))
    assert tx1.validate() is True
    tx1.save(block_height=1, tx_index=0)

    tx2 = Transaction(
        chain=1, nonce=2, fee=100, value=2_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    )
    tx2 = tx2.sign(unhexlify(WALLET_1["private_key"]))
    assert tx2.validate() is True
