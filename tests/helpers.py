# helpers.py

from tests.constants import WALLET_1, WALLET_2, WALLET_3
from binascii import unhexlify
from luracoin.transactions import Transaction


def add_test_transactions():
    transaction1 = Transaction(
        chain=1,
        nonce=1,
        fee=57000,
        value=5_000_000,
        to_address=WALLET_2["address"],
    )

    transaction1 = transaction1.sign(unhexlify(WALLET_1["private_key"]))
    assert transaction1.validate() == True
    transaction1.to_transaction_pool()

    transaction2 = Transaction(
        chain=1,
        nonce=1,
        fee=157_000,
        value=15_000_000,
        to_address=WALLET_3["address"],
    )

    transaction2 = transaction2.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction2.validate() == True
    transaction2.to_transaction_pool()

    transaction3 = Transaction(
        chain=1,
        nonce=2,
        fee=5700,
        value=500_000,
        to_address=WALLET_1["address"],
    )

    transaction3 = transaction3.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction3.validate() == True
    transaction3.to_transaction_pool()

    transaction4 = Transaction(
        chain=1, nonce=2, fee=50, value=100, to_address=WALLET_1["address"]
    )

    transaction4 = transaction4.sign(unhexlify(WALLET_2["private_key"]))
    assert transaction4.validate() == True
    transaction4.to_transaction_pool()

    transaction5 = Transaction(
        chain=1, nonce=2, fee=150, value=600, to_address=WALLET_2["address"]
    )

    transaction5 = transaction5.sign(unhexlify(WALLET_3["private_key"]))
    assert transaction5.validate() == True
    transaction5.to_transaction_pool()

    return [
        transaction1,
        transaction2,
        transaction3,
        transaction4,
        transaction5,
    ]
