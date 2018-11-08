from luracoin.transactions import Transaction, TxIn, TxOut, OutPoint
from luracoin.wallet import build_p2pkh


def test_transaction_serialize(transaction1):
    assert transaction1.serialize() == (
        "01000100000000000000000000000000000000000000000000000000000000000000"
        "00ffffffff0100000000003005ed0b2000000003476a9150087a6532f90c45ef5cfd"
        "d7f90948b2a0fc383dd1b88ac002f6859000000003476a9150087a6532f90c45ef5c"
        "fdd7f90948b2a0fc383dd1b88ac0065cd1d000000003476a9150087a6532f90c45ef"
        "5cfdd7f90948b2a0fc383dd1b88ac"
    )


def test_transaction_id(transaction1):
    assert (
        transaction1.id
        == "c2821034a332fad997e38281f8d9d6ac765171ac41f9c761f9d0cc54e02a17ee"
    )


def test_transaction_is_coinbase(transaction1, transaction2):
    assert transaction1.is_coinbase is True
    assert transaction2.is_coinbase is False


def test_transaction_validate(transaction1, transaction2):
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
