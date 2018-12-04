from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.wallet import build_p2pkh


def test_transaction_serialize(transaction1):  # type: ignore
    assert transaction1.serialize() == (
        "01000146914795faa733b4beee8f7fa4e2e7522f4d9d533d1fb7cd252e0d379dcdde"
        "c1000000000100000000001d0090000000000003476a915002fb168b47d7cb54b07c"
        "7a4c4f7c005811f0a775d88ac"
    )


def test_transaction_id(transaction1):  # type: ignore
    assert transaction1.id == (
        "dc75fe6eaaab2646f78a56027c0344ff5ad7e8a4417bd49bab9093cd580971a9"
    )


def test_transaction_is_not_coinbase(transaction1, transaction2):  # type: ignore
    assert transaction1.is_coinbase is False
    assert transaction2.is_coinbase is False


def test_transaction_is_coinbase(coinbase_transaction1, coinbase_transaction2):  # type: ignore
    assert coinbase_transaction1.is_coinbase is True
    assert coinbase_transaction2.is_coinbase is True


def test_transaction_validate(transaction1, transaction2):  # type: ignore
    assert transaction1.validate() is True
    assert transaction2.validate() is True

    tx = Transaction(
        version=1,
        txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig="0", sequence=0)],
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
