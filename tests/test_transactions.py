from luracoin.config import Config
from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.wallet import build_p2pkh


def test_transaction_serialize(transaction1):  # type: ignore
    assert transaction1.serialize() == (
        "0100014ac727f587761a17f5a3b63de589959989c655b579d261361ebaa287954440"
        "a5000000000100000000001d0090000000000003476a915002fb168b47d7cb54b07c"
        "7a4c4f7c005811f0a775d88ac"
    )


def test_transaction_id(transaction1):  # type: ignore
    assert transaction1.id == (
        "151b3b83f5a976279416b00200717120261d377632b5fef66cff076d34330383"
    )


def test_transaction_is_not_coinbase(  # type: ignore
    transaction1, transaction2
):
    assert transaction1.is_coinbase is False
    assert transaction2.is_coinbase is False


def test_transaction_is_coinbase(coinbase_tx1, coinbase_tx2):  # type: ignore
    assert coinbase_tx1.is_coinbase is True
    assert coinbase_tx2.is_coinbase is True


def test_transaction_validate(transaction1, transaction2):  # type: ignore
    assert transaction1.validate() is True
    assert transaction2.validate() is True


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
