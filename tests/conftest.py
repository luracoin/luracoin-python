from luracoin.transactions import Transaction, TxIn, TxOut, OutPoint
from luracoin.wallet import build_p2pkh
import pytest


@pytest.fixture
def transaction1() -> Transaction:
    tx = Transaction(
        version=1,
        txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig="0", sequence=0)],
        txouts=[
            TxOut(
                value=3_000_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            ),
            TxOut(
                value=1_500_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            ),
            TxOut(
                value=500_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            ),
        ],
        locktime=0,
    )
    return tx


@pytest.fixture
def transaction2() -> Transaction:
    prev_tx_id = (
        "c2821034a332fad997e38281f8d9d6ac765171ac41f9c761f9d0cc54e02a17ee"
    )
    tx = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(prev_tx_id, 0),
                unlock_sig="0",
                sequence=0,
            )
        ],
        txouts=[
            TxOut(
                value=3_000_000_000,
                to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
            )
        ],
        locktime=0,
    )
    return tx
