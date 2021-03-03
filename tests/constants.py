from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.wallet import build_p2pkh
from luracoin.config import Config

BLOCK3_VALID_NONCE = 2_615_155


COINBASE1 = Transaction(
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

COINBASE2 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="2",
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

COINBASE3 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="3",
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

COINBASE4 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="4",
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

COINBASE5 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="5",
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

COINBASE6 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="6",
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

COINBASE7 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="7",
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

COINBASE8 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="8",
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


COINBASE9 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
            unlock_sig="9",
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

TRANSACTION1 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(COINBASE1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=2512,
            to_address=build_p2pkh("15MBHcN8xZ23ZCeeGp4JzYi7HsSSsz5qdv"),
        )
    ],
    locktime=0,
)

TRANSACTION2 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(COINBASE1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=10_000_000,
            to_address=build_p2pkh("1Ky33SmpvgRTHu4PMpDxo9QcAnRGd8WWNk"),
        )
    ],
    locktime=0,
)

TRANSACTION3 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(COINBASE1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=200_000_000,
            to_address=build_p2pkh("14rBe5KWh2fhw4TbLSS7tGuYvXkBSDiZby"),
        )
    ],
    locktime=0,
)

TRANSACTION4 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(COINBASE1.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=510_000,
            to_address=build_p2pkh("1ByCQKMDiRM1cp14vrpz4HCBz7A6LJ5XJ8"),
        )
    ],
    locktime=0,
)

TRANSACTION5 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(COINBASE1.id, 1), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=510_000,
            to_address=build_p2pkh("17Gu7GNgs13qr9M3edFdaspdA6u4aJF6Dc"),
        )
    ],
    locktime=0,
)


TRANSACTION6 = Transaction(
    version=1,
    txins=[
        TxIn(to_spend=OutPoint(TRANSACTION5.id, 0), unlock_sig="0", sequence=0)
    ],
    txouts=[
        TxOut(
            value=110_000,
            to_address=build_p2pkh("17Gu7GNgs13qr9M3edFdaspdA6u4aJF6Dc"),
        ),
        TxOut(
            value=150_000,
            to_address=build_p2pkh("14rBe5KWh2fhw4TbLSS7tGuYvXkBSDiZby"),
        ),
        TxOut(
            value=50000,
            to_address=build_p2pkh("1Ky33SmpvgRTHu4PMpDxo9QcAnRGd8WWNk"),
        ),
        TxOut(
            value=175_000,
            to_address=build_p2pkh("1ByCQKMDiRM1cp14vrpz4HCBz7A6LJ5XJ8"),
        ),
    ],
    locktime=0,
)
