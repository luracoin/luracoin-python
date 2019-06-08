import ecdsa
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
from tests.transactions.constants import TRANSACTION1
from luracoin.helpers import bytes_to_signing_key


def test_transaction_serialize():
    assert TRANSACTION1.serialize() == (
        "01000173837e92739d17dbdddd86719c605eebcb161f948a667bd747b03b819ad46c"
        "3100000000fd040180c6092f3dce23e1cf334f7d38bb05090253f54b2b92b1fcd670"
        "c4f3705dc2029580e1702b39d3457bb8c7e3292fa47f51d3e5af73be8e169ea73a88"
        "b5ddf994308079b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad3"
        "21e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65"
        "b3ee0000000001d0090000000000002a00b80ffa0c3ff87a882e002ef9dedeed773c"
        "af367d"
    )


def test_transaction_id(transaction1):  # type: ignore
    assert transaction1.id == (
        "9283b3ed5b11af9f46a4e0085bca6cfee07188a945c57a47a9d32bf0912fe88a"
    )


def test_transaction_is_not_coinbase(  # type: ignore
    transaction1, transaction2
):
    assert transaction1.is_coinbase is False
    assert transaction2.is_coinbase is False


def test_transaction_is_coinbase(coinbase_tx1, coinbase_tx2):  # type: ignore
    assert coinbase_tx1.is_coinbase is True
    assert coinbase_tx2.is_coinbase is True
