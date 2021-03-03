import ecdsa
import json
import msgpack
from luracoin.config import Config
from luracoin.transactions import (
    OutPoint,
    Transaction,
    TxIn,
    TxOut,
    transaction_chainstate_serialise,
    transaction_chainstate_deserialise,
    build_message,
    build_script_sig,
    verify_signature,
    is_valid_unlocking_script,
    deserialize_unlocking_script,
    sign_transaction,
)
from luracoin.wallet import build_p2pkh, pubkey_to_address, address_to_pubkey
from tests.transactions.constants import TRANSACTION1, TRANSACTION6
from luracoin.helpers import bytes_to_signing_key


def test_transaction_input_serialize():
    assert TRANSACTION1.txins[0].serialize() == (
        b"\x83\xa8to_spend\x92\xd9@4543907dbea254f6db47a012f14396027061eeb728"
        b"a7cb846fe6d9590a3f2e09\x00\xaaunlock_sig\xda\x01\x0480c6092f3dce23e"
        b"1cf334f7d38bb05090253f54b2b92b1fcd670c4f3705dc2029580e1702b39d3457b"
        b"b8c7e3292fa47f51d3e5af73be8e169ea73a88b5ddf994308079b043fbab0aa455d"
        b"0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585de"
        b"bfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee\xa8sequence\x00"
    )


def test_transaction_output_serialize():
    assert TRANSACTION1.txouts[0].serialize() == (
        b"\x82\xa5value\xcd\t\xd0\xaato_address\xd9*00b80ffa0c3ff87a882e002ef"
        b"9dedeed773caf367d"
    )


def test_transaction_serialize():
    expected_serialisation = (
        b"\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@f422efbd54"
        b"b52696a86e11625ec8d7aaf7f9c88fba01605cd71e08a8c09bf1cc\x00\xaaunloc"
        b"k_sig\xda\x01\x0480b1eb302b6f5bbbd8b970800c63a1e8c285ab06fe7cfe0d37"
        b"21969ac4707a7b31028c07676936144b9dc0ac71fc0edbefcc76dcaf7e61f5963e9"
        b"da669eaa1aa7980f4b076bfcdb1f782018d2e3afa195ae1c92f18b3f97ba0ca1a99"
        b"23bd48291817f8ba9a2dbe2fd347b5a75998221022a548c9bfb326704c021870ccc"
        b"e90c6e1df\xa8sequence\x00\xa6txouts\x94\x82\xa5value\xce\x00\x01"
        b"\xad\xb0\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
        b"1b\x82\xa5value\xce\x00\x02I\xf0\xaato_address\xd9*00112c3926e5e63e"
        b"f39aae10a1b5cf0f57f54d6752\x82\xa5value\xcd\xc3P\xaato_address\xd9*"
        b"00827c5733e1401c1daaaaa3739ed5ad2acfd9ce4a\x82\xa5value\xce\x00\x02"
        b"\xab\x98\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
        b"1b\xa8locktime\x00"
    )

    assert TRANSACTION6.serialize() == expected_serialisation


def test_transaction_deserialize():
    tx = Transaction()
    tx.deserialize(
        b"\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@f422efbd54"
        b"b52696a86e11625ec8d7aaf7f9c88fba01605cd71e08a8c09bf1cc\x00\xaaunloc"
        b"k_sig\xda\x01\x0480b1eb302b6f5bbbd8b970800c63a1e8c285ab06fe7cfe0d37"
        b"21969ac4707a7b31028c07676936144b9dc0ac71fc0edbefcc76dcaf7e61f5963e9"
        b"da669eaa1aa7980f4b076bfcdb1f782018d2e3afa195ae1c92f18b3f97ba0ca1a99"
        b"23bd48291817f8ba9a2dbe2fd347b5a75998221022a548c9bfb326704c021870ccc"
        b"e90c6e1df\xa8sequence\x00\xa6txouts\x94\x82\xa5value\xce\x00\x01"
        b"\xad\xb0\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
        b"1b\x82\xa5value\xce\x00\x02I\xf0\xaato_address\xd9*00112c3926e5e63e"
        b"f39aae10a1b5cf0f57f54d6752\x82\xa5value\xcd\xc3P\xaato_address\xd9*"
        b"00827c5733e1401c1daaaaa3739ed5ad2acfd9ce4a\x82\xa5value\xce\x00\x02"
        b"\xab\x98\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
        b"1b\xa8locktime\x00"
    )

    assert tx.json() == TRANSACTION6.json()
    assert tx.id == TRANSACTION6.id
