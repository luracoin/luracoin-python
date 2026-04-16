from binascii import unhexlify
from luracoin.transactions import Transaction, is_valid_unlocking_script
from tests.constants import WALLET_1, WALLET_2


def test_signature_with_matching_from_address_is_valid():
    """
    A transaction signed by WALLET_1 should be valid when
    from_address=WALLET_1["address"].
    """
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert is_valid_unlocking_script(
        unlocking_script=tx.unlock_sig,
        transaction_serialized=tx.serialize(to_sign=True).hex(),
        from_address=WALLET_1["address"],
    ) is True


def test_signature_with_wrong_from_address_is_rejected():
    """
    A transaction signed by WALLET_1 must be REJECTED when
    from_address=WALLET_2["address"].
    """
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert is_valid_unlocking_script(
        unlocking_script=tx.unlock_sig,
        transaction_serialized=tx.serialize(to_sign=True).hex(),
        from_address=WALLET_2["address"],
    ) is False
