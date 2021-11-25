import json
from pymongo import MongoClient
from random import randint
from luracoin.transactions import (
    Transaction,
    sign_transaction,
    is_valid_unlocking_script,
)
from luracoin.config import Config


def test_to_json():
    transacion = Transaction(
        chain=1,
        nonce=8763,
        fee=100,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=b"~\xf8su\xeb\xeb\xc9\xd4\xcd\r\x17\x08\xe5#Oo\x05D\x85\x94\x04\x88\x8f\xf9\xcb\xfc\x9amzdG\xb4.\xdc\xac\x14\xcc\x95\x8cI\x9e\xfer\xe4\x051(\x08\x8e5\x0f(]s\x89g\xe7|\xd9\xee\xf8'B\x17\xb8\xb2\x14\xfc\x03\x87;b\xab\xcc^\xfc\xf5\xee\x84\\'h\xe0\x97\xe2\xaeI+\x9al\xe3;:~;]3l,\xab[^v\xef&E\x9d\xbaS\x1c\xe2\x04\xcaC\x15W\x9fR0\xc6}\xe4\xe6\x80\x99\xdf!\x15",
    )

    assert transacion.json() == {
        "id": "d24b6dae6bc576b367ac29a981727d221b9e1211280dc4bb24a4c4d2808c82f0",
        "chain": 1,
        "nonce": 8763,
        "fee": 100,
        "value": 50000,
        "to_address": "1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        "unlock_sig": "7ef87375ebebc9d4cd0d1708e5234f6f0544859404888ff9cbfc9a6d7a6447b42edcac14cc958c499efe72e4053128088e350f285d738967e77cd9eef8274217b8b214fc03873b62abcc5efcf5ee845c2768e097e2ae492b9a6ce33b3a7e3b5d336c2cab5b5e76ef26459dba531ce204ca4315579f5230c67de4e68099df2115",
    }


def test_transaction_serializer_to_sign():
    transaction_original = Transaction(
        chain=1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    )

    expected_serialization_hex = "01ffffffffa8de0000404b4c00000000003148374e7455454e7245627753566d3532664865507a426e75345733624371696d50"
    expected_serialization_bytes = b"\x01\xff\xff\xff\xff\xa8\xde\x00\x00@KL\x00\x00\x00\x00\x001H7NtUENrEbwSVm52fHePzBnu4W3bCqimP"

    assert (
        transaction_original.serialize(to_sign=True).hex()
        == expected_serialization_hex
    )
    assert (
        transaction_original.serialize(to_sign=True)
        == expected_serialization_bytes
    )

    transaction = Transaction()
    transaction.deserialize(expected_serialization_bytes)

    assert transaction_original.json() == transaction.json()


def test_serializer_with_coinbase_signatures():
    transaction_original = Transaction(
        chain=1,
        nonce=4_294_967_295,
        fee=57000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    expected_serialization_hex = "01ffffffffa8de0000404b4c00000000003148374e7455454e7245627753566d3532664865507a426e75345733624371696d500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    expected_serialization_bytes = b"\x01\xff\xff\xff\xff\xa8\xde\x00\x00@KL\x00\x00\x00\x00\x001H7NtUENrEbwSVm52fHePzBnu4W3bCqimP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    assert transaction_original.serialize().hex() == expected_serialization_hex
    assert transaction_original.serialize() == expected_serialization_bytes

    transaction = Transaction()
    transaction.deserialize(expected_serialization_bytes)

    assert transaction_original.json() == transaction.json()


def test_signatures(mocker):
    PRIVATE_KEY_1 = (
        b"\xb1\x80E\xceRo\xfeG[\x89\xe2\xc1+\xfd\xf9\xc4"
        b"\x80w\x91\x836o~\xbe\x87\x82bb\xab@\xf9N"
    )

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
