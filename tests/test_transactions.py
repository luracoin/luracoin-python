import json
from pymongo import MongoClient
from random import randint
from luracoin.transactions import (
    Transaction,
    sign_transaction,
    is_valid_unlocking_script,
)

def test_transaction_to_json():
    transacion = Transaction(
        chain=1,
        nonce=8763,
        fee=100,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig="unlicking signature"
    )

    assert transacion.json() == {
        'chain': 1, 
        'nonce': 8763, 
        'fee': 100, 
        'value': 50000, 
        'to_address': '1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP', 
        'unlock_sig': 'unlicking signature'
    }


def test_transaction_serializer_without_signatures():
    transaction_original = Transaction(
        chain=1,
        nonce=4294967295,
        fee=57_000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    )

    expected_serialization_hex = "01ffffffffa8de0000404b4c00000000003148374e7455454e7245627753566d3532664865507a426e75345733624371696d50"
    expected_serialization_bytes = b"\x01\xff\xff\xff\xff\xa8\xde\x00\x00@KL\x00\x00\x00\x00\x001H7NtUENrEbwSVm52fHePzBnu4W3bCqimP"

    assert transaction_original.serialize(to_sign=True).hex() == expected_serialization_hex
    assert transaction_original.serialize(to_sign=True) == expected_serialization_bytes

    transaction = Transaction()
    transaction.deserialize(expected_serialization_hex)

    assert transaction_original.json() == transaction.json()


def test_transaction_signatures():
    PRIVATE_KEY_1 = (
        b"\xb1\x80E\xceRo\xfeG[\x89\xe2\xc1+\xfd\xf9\xc4"
        b"\x80w\x91\x836o~\xbe\x87\x82bb\xab@\xf9N"
    )
    transaction_original = Transaction(
        chain=1,
        nonce=4294967295,
        fee=57_000,
        value=5_000_000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    )

    expected_serialization_hex = "01ffffffffa8de0000404b4c00000000003148374e7455454e7245627753566d3532664865507a426e75345733624371696d50"

    assert transaction_original.serialize(to_sign=True).hex() == expected_serialization_hex

    signature = sign_transaction(
        private_key=PRIVATE_KEY_1, 
        transaction_serialized=expected_serialization_hex,
    )

    print("Signature")
    print(signature)

    transaction_original.unlock_sig = signature
    print(json.dumps(transaction_original.json(), indent=2))

    is_valid = is_valid_unlocking_script(
        unlocking_script=transaction_original.unlock_sig,
        transaction_serialized=expected_serialization_hex
    )

    print(is_valid)

    assert False