import pytest

from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.wallet import build_p2pkh
from luracoin.pow import proof_of_work


coinbase1 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
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

coinbase2 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="1",
            sequence=0,
        )
    ],
    txouts=[
        TxOut(
            value=5_000_000_000,
            to_address=build_p2pkh("1DsrJ4PPKTxTLCtr5TYDHrcWo3FZ2aog86"),
        )
    ],
    locktime=0,
)

tx1 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(coinbase1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=2512,
            to_address=build_p2pkh("15MBHcN8xZ23ZCeeGp4JzYi7HsSSsz5qdv"),
        )
    ],
    locktime=0,
)

tx2 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(coinbase1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=10_000_000,
            to_address=build_p2pkh("1Ky33SmpvgRTHu4PMpDxo9QcAnRGd8WWNk"),
        )
    ],
    locktime=0,
)

tx3 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(coinbase1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=200_000_000,
            to_address=build_p2pkh("14rBe5KWh2fhw4TbLSS7tGuYvXkBSDiZby"),
        )
    ],
    locktime=0,
)

tx4 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(coinbase1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=510_000,
            to_address=build_p2pkh("1ByCQKMDiRM1cp14vrpz4HCBz7A6LJ5XJ8"),
        )
    ],
    locktime=0,
)

tx5 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(coinbase1.id, 1), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=510_000,
            to_address=build_p2pkh("17Gu7GNgs13qr9M3edFdaspdA6u4aJF6Dc"),
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
        nonce=0,
    )
    block.txns = [coinbase1]
    return block


@pytest.fixture
def block2() -> Block:
    print("Hey")
    print(proof_of_work(block1().id, 2))
    block = Block(
        version=1,
        prev_block_hash=block1().id,
        timestamp=1_501_821_412,
        bits=24,
        nonce=76,
    )
    block.txns = [coinbase2, tx1, tx2, tx3, tx4, tx5]
    return block


@pytest.fixture
def coinbase_tx1() -> Transaction:
    return coinbase1


@pytest.fixture
def coinbase_tx2() -> Transaction:
    return coinbase2


@pytest.fixture
def transaction1() -> Transaction:
    return tx1


@pytest.fixture
def transaction2() -> Transaction:
    return tx2


@pytest.fixture
def transaction3() -> Transaction:
    return tx3


@pytest.fixture
def transaction4() -> Transaction:
    return tx4


@pytest.fixture
def transaction5() -> Transaction:
    return tx5
