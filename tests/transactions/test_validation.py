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
from tests.constants import COINBASE2, COINBASE1
from tests.transactions.constants import (
    TRANSACTION1,
    TRANSACTION2,
    TRANSACTION3,
    TRANSACTION4,
    TRANSACTION5,
    TRANSACTION6,
    TRANSACTION7,
)
from luracoin.helpers import bytes_to_signing_key


def test_transaction_validate():
    assert TRANSACTION1.validate() is True
    assert TRANSACTION2.validate() is True
    assert TRANSACTION3.validate() is True
    assert TRANSACTION4.validate() is True
    assert TRANSACTION5.validate() is True
    assert TRANSACTION6.validate() is True
    assert TRANSACTION7.validate() is False


def test_invalid_signature():
    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION1.txins[0].unlock_sig,
        outpoint=TRANSACTION1.txins[0].to_spend,
    )
    assert TRANSACTION1.validate() is True

    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION2.txins[0].unlock_sig,
        outpoint=TRANSACTION2.txins[0].to_spend,
    )
    assert TRANSACTION2.validate() is True

    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION3.txins[0].unlock_sig,
        outpoint=TRANSACTION3.txins[0].to_spend,
    )
    assert TRANSACTION3.validate() is True

    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION4.txins[0].unlock_sig,
        outpoint=TRANSACTION4.txins[0].to_spend,
    )
    assert TRANSACTION4.validate() is True

    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION5.txins[0].unlock_sig,
        outpoint=TRANSACTION5.txins[0].to_spend,
    )
    assert TRANSACTION5.validate() is True

    assert is_valid_unlocking_script(
        unlocking_script=TRANSACTION6.txins[0].unlock_sig,
        outpoint=TRANSACTION6.txins[0].to_spend,
    )
    assert TRANSACTION6.validate() is True

    assert not is_valid_unlocking_script(
        unlocking_script=TRANSACTION7.txins[0].unlock_sig,
        outpoint=TRANSACTION7.txins[0].to_spend,
    )
    assert TRANSACTION7.validate() is False


def test_transaction_invalid__reward():  # type: ignore
    tx = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(
                    Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX
                ),
                unlock_sig="0",
                sequence=0,
            )
        ],
        txouts=[
            TxOut(
                value=3_000_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            ),
            TxOut(
                value=2_500_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            ),
        ],
        locktime=0,
    )

    assert tx.validate() is False


def test_transaction_invalid__empty_txins():  # type: ignore
    tx = Transaction(
        version=1,
        txins=[],
        txouts=[
            TxOut(
                value=100_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            )
        ],
        locktime=0,
    )

    assert tx.validate() is False


def test_transaction_invalid__empty_txouts():  # type: ignore
    tx = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(
                    Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX
                ),
                unlock_sig="0",
                sequence=0,
            )
        ],
        txouts=[],
        locktime=0,
    )

    assert tx.validate() is False


def test_transaction_invalid__unlocking():  # type: ignore
    coinbase1 = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(
                    Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX
                ),
                unlock_sig="0",
                sequence=0,
            )
        ],
        txouts=[
            TxOut(
                value=3_000_000_000,
                to_address=build_p2pkh("1QHxaBNsCtYXj8M6CUi7fUeNY2FE2m7t8e"),
            ),
            TxOut(
                value=1_500_000_000,
                to_address=build_p2pkh("16iFwTZFLhDVY3sK1K3oBRLNkJCjHBJv1E"),
            ),
            TxOut(
                value=500_000_000,
                to_address=build_p2pkh("1ByCQKMDiRM1cp14vrpz4HCBz7A6LJ5XJ8"),
            ),
        ],
        locktime=0,
    )

    tx1 = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(coinbase1.id, 0), unlock_sig="0", sequence=0
            )
        ],
        txouts=[
            TxOut(
                value=2512,
                to_address=build_p2pkh("15MBHcN8xZ23ZCeeGp4JzYi7HsSSsz5qdv"),
            )
        ],
        locktime=0,
    )

    assert tx1.validate() is False
