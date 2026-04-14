# helpers.py

from tests.constants import WALLET_1, WALLET_2, WALLET_3
from binascii import unhexlify
from luracoin.transactions import Transaction
from luracoin.chain import Chain


def add_test_transactions():
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 100_000_000, "nonce": 0})
    chain.set_account(WALLET_2["address"], {"balance": 100_000_000, "nonce": 0})
    chain.set_account(WALLET_3["address"], {"balance": 100_000_000, "nonce": 1})

    transaction1 = Transaction(
        chain=1,
        nonce=1,
        fee=57000,
        value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )

    transaction1 = transaction1.sign(unhexlify(WALLET_1["private_key"]))
    assert transaction1.validate() == True

    transaction2 = Transaction(
        chain=1,
        nonce=1,
        fee=157_000,
        value=15_000_000,
        from_address=WALLET_2["address"],
        to_address=WALLET_3["address"],
    )

    transaction2 = transaction2.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction2.validate() == True

    # Save tx2 so WALLET_2 nonce updates to 1
    transaction2.save(block_height=0, tx_index=1)

    transaction3 = Transaction(
        chain=1,
        nonce=2,
        fee=5700,
        value=500_000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )

    transaction3 = transaction3.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction3.validate() == True

    # Save tx3 so WALLET_2 nonce updates to 2
    transaction3.save(block_height=0, tx_index=2)

    transaction4 = Transaction(
        chain=1, nonce=3, fee=50, value=100,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )

    transaction4 = transaction4.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction4.validate() == True

    # Save tx1 so WALLET_1 nonce updates to 1
    transaction1.save(block_height=0, tx_index=0)

    transaction5 = Transaction(
        chain=1, nonce=2, fee=150, value=600,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )

    transaction5 = transaction5.sign(unhexlify(WALLET_1["private_key"]))
    assert transaction5.validate() == True

    return [
        transaction1,
        transaction2,
        transaction3,
        transaction4,
        transaction5,
    ]
