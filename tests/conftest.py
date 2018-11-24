import pytest

from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.wallet import build_p2pkh

tx1 = Transaction(
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

prev_tx_id = "c2821034a332fad997e38281f8d9d6ac765171ac41f9c761f9d0cc54e02a17ee"

tx2 = Transaction(
    version=1,
    txins=[TxIn(to_spend=OutPoint(prev_tx_id, 0), unlock_sig="0", sequence=0)],
    txouts=[
        TxOut(
            value=3_000_000_000,
            to_address=build_p2pkh("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"),
        )
    ],
    locktime=0,
)


@pytest.fixture
def block1() -> Block:
    block = Block(
        version=1,
        prev_block_hash=Config.COINBASE_TX_ID,
        timestamp=1_501_821_412,
        bits=24,
        nonce=10_126_761,
        txns=[tx1],
    )
    return block


@pytest.fixture
def transaction1() -> Transaction:
    return tx1


@pytest.fixture
def transaction2() -> Transaction:
    return tx2
