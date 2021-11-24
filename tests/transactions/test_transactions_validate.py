import pytest
import json
import binascii
from binascii import unhexlify
from pymongo import MongoClient
from random import randint
from luracoin.transactions import (
    Transaction,
    sign_transaction,
    is_valid_unlocking_script,
)
from luracoin.config import Config
from luracoin.exceptions import TransactionNotValid
from luracoin import errors
from tests.constants import WALLET_1, WALLET_2, WALLET_3


PRIVATE_KEY_1 = (
    b"\xb1\x80E\xceRo\xfeG[\x89\xe2\xc1+\xfd\xf9\xc4"
    b"\x80w\x91\x836o~\xbe\x87\x82bb\xab@\xf9N"
)

def test_validate_signatures(mocker):
    """
    Test to check that the signatures are valid.
    """
    transaction_original = Transaction(
        chain=1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    )

    transaction = transaction_original.sign(PRIVATE_KEY_1)
    assert transaction.validate() == True

    # Incorrect Public Key / Signature
    with mocker.patch(
        "luracoin.transactions.deserialize_unlocking_script",
        return_value={
            "signature": "6cfa3bd7427ec06e8c0e93911db0932fa18f763f617f4115929501affd0f95aacc71c66d0c7c535f3843d537cb5c424bb0ee59e5baf6df8966c6b58faa2abfc2",
            "public_key": "533b17c5cf044c799a67ad974250aeb72cb529ae59f4b8804adc6eb602dd5ee35c6f8a1910dd7924f89a624456f3c0f4e2c6d4117ee0fa7419af6c7ca120d596",
            "address": "1C5fcCCJydpyQ7KqHBuGHJbwrwURHd62Lj",
        },
    ):
        assert transaction.validate() == False

    # Invalid Public Key
    with mocker.patch(
        "luracoin.transactions.deserialize_unlocking_script",
        return_value={
            "signature": "6cfa3bd7427ec06e8c0e93911db0932fa18f763f617f4115929501affd0f95aacc71c66d0c7c535f3843d537cb5c424bb0ee59e5baf6df8966c6b58faa2abfc2",
            "public_key": "0000000000000455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee",
            "address": "1C5fcCCJydpyQ7KqHBuGHJbwrwURHd62Lj",
        },
    ):
        assert transaction.validate() == False

    transaction.to_transaction_pool()


def test_modify_transaction_after_signing(mocker):
    """
    Test to check that you can't modify a transaction after signing it.
    """
    transaction_original = Transaction(
        chain=0,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    )

    transaction = transaction_original.sign(PRIVATE_KEY_1)
    transaction.value = 10_000_000

    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_INVALID_SIGNATURE
    ):
        transaction.validate(raise_exception=True)


def test_chain(mocker):
    """
    Test to validate the field 'chain' from a transaction.
    """
    transaction = Transaction(
        chain=-1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_CHAIN
    ):
        transaction.validate(raise_exception=True)

    transaction.chain = 15
    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.chain = 257
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_CHAIN
    ):
        transaction.validate(raise_exception=True)


def test_nonce(mocker):
    """
    Test to validate the field 'nonce' from a transaction
    """
    transaction = Transaction(
        chain=0,
        nonce=14_294_967_296,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_NONCE
    ):
        transaction.validate(raise_exception=True)

    transaction.nonce = 1_260_300
    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.nonce = -1
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_NONCE
    ):
        transaction.validate(raise_exception=True)


def test_fee(mocker):
    """
    Test to validate the field 'fee' from a transaction
    """
    transaction = Transaction(
        chain=0,
        nonce=0,
        fee=4_294_967_296,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_FEE
    ):
        transaction.validate(raise_exception=True)

    transaction.fee = 5_000_000
    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.fee = -1
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_FEE
    ):
        transaction.validate(raise_exception=True)


def test_value(mocker):
    """
    Test to validate the field 'value' from a transaction
    """
    transaction = Transaction(
        chain=0,
        nonce=0,
        fee=0,
        value=18_446_744_073_709_551_616,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_VALUE
    ):
        transaction.validate(raise_exception=True)

    transaction.value = 18_446_744_073_709_551_615
    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.value = 9_551_615
    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.value = 0
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_VALUE
    ):
        transaction.validate(raise_exception=True)

    transaction.value = -1
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_VALUE
    ):
        transaction.validate(raise_exception=True)


def test_to_address(mocker):
    """
    Test to validate the field 'to_address' from a transaction
    """
    transaction = Transaction(
        chain=1,
        nonce=10,
        fee=50,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() == True
    assert transaction.validate(raise_exception=True) == True

    transaction.to_address = "1H7NtUENrEbwSVm52fHePzBnu4W3bCqimPX"
    assert transaction.validate() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_TO_ADDRESS
    ):
        transaction.validate(raise_exception=True)


def test_unlock_sig(mocker):
    """
    Test to validate the field 'unlock_sig' from a transaction
    """
    transaction = Transaction(
        chain=1,
        nonce=10,
        fee=50,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate_fields() == True
    assert transaction.validate_fields(raise_exception=True) == True

    transaction.unlock_sig = binascii.unhexlify("0" * 258)
    assert transaction.validate_fields() == False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_FIELD_SIGNATURE
    ):
        transaction.validate_fields(raise_exception=True)

    transaction.unlock_sig = binascii.unhexlify("1" * 256)
    assert transaction.validate_fields() == True
    assert transaction.validate_fields(raise_exception=True) == True


def test_staking_transaction():
    transaction = Transaction(
        chain=1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address=Config.STAKING_ADDRESS,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    assert transaction.validate() is False
    with pytest.raises(
        TransactionNotValid, match=errors.TRANSACTION_INVALID_STAKING
    ):
        transaction.validate_fields(raise_exception=True)

    transaction = Transaction(
        chain=1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address=Config.STAKING_ADDRESS,
    )

    transaction = transaction.sign(unhexlify(WALLET_1["private_key"]))

    assert transaction.validate() is True