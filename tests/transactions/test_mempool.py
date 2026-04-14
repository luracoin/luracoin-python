from luracoin.transactions import Transaction
from luracoin.chain import Chain
from tests.constants import WALLET_1, WALLET_2


def test_to_transaction_pool_rejects_invalid_fields():
    """Transaction with invalid fields should not be accepted into mempool."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=0,  # value=0 is invalid
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=b"\x00" * 128,
    )

    result = tx.to_transaction_pool()
    assert result is False


def test_to_transaction_pool_rejects_no_balance():
    """Transaction from account with no balance should be rejected."""
    from binascii import unhexlify

    # No account set up for WALLET_1
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    result = tx.to_transaction_pool()
    assert result is False
