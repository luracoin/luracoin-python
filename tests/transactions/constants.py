from luracoin.transactions import (
    OutPoint,
    Transaction,
    TxIn,
    TxOut,
    sign_transaction,
    build_script_sig,
)
from luracoin.wallet import build_p2pkh
from luracoin.config import Config
from tests.wallet.constants import (
    PUBLIC_KEY_1,
    PRIVATE_KEY_1,
    ADDRESS_1,
    PUBLIC_KEY_2,
    PRIVATE_KEY_2,
    ADDRESS_2,
    PUBLIC_KEY_3,
    PRIVATE_KEY_3,
    ADDRESS_3,
    PUBLIC_KEY_4,
    PRIVATE_KEY_4,
    ADDRESS_4,
    PUBLIC_KEY_5,
    PRIVATE_KEY_5,
    ADDRESS_5,
)

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
        TxOut(value=3_000_000_000, to_address=build_p2pkh(ADDRESS_1)),
        TxOut(value=1_500_000_000, to_address=build_p2pkh(ADDRESS_2)),
        TxOut(value=500_000_000, to_address=build_p2pkh(ADDRESS_3)),
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
    txouts=[TxOut(value=5_000_000_000, to_address=build_p2pkh(ADDRESS_1))],
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
    txouts=[TxOut(value=5_000_000_000, to_address=build_p2pkh(ADDRESS_2))],
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
    txouts=[TxOut(value=5_000_000_000, to_address=build_p2pkh(ADDRESS_2))],
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
    txouts=[TxOut(value=5_000_000_000, to_address=build_p2pkh(ADDRESS_1))],
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
    txouts=[TxOut(value=5_000_000_000, to_address=build_p2pkh(ADDRESS_2))],
    locktime=0,
)

# TRANSACTION 1
unlock_sig_1 = (
    "80c6092f3dce23e1cf334f7d38bb05090253f54b2b92b1fcd670c4f3705dc2029580e170"
    "2b39d3457bb8c7e3292fa47f51d3e5af73be8e169ea73a88b5ddf994308079b043fbab0a"
    "a455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585de"
    "bfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee"
)
TRANSACTION1 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(COINBASE1.id, 0),
            unlock_sig=unlock_sig_1,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=2512, to_address=build_p2pkh(ADDRESS_4))],
    locktime=0,
)

# TRANSACTION 2
unlock_sig_2 = (
    "80b8335f155ee93b835ccf0d5aa96fd53146185a1e7d80d3621f5e31d0b1a83185edf763"
    "8b6511af8faae029cb4b5be346cb3be8980ca5d98d92bb518a36cc2cf3807b11afeeb5e0"
    "a40d14541774c5cf8db6c22dfc98594ca880270fe6fc12f29da564d90f3cc829e18d1879"
    "388dacc931fbbc43fa1c4479f4798cf1c82da103e398"
)
TRANSACTION2 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(COINBASE1.id, 1),
            unlock_sig=unlock_sig_2,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=10_000_000, to_address=build_p2pkh(ADDRESS_5))],
    locktime=0,
)

# TRANSACTION 3
unlock_sig_3 = (
    "805ca938bb968991c1a5263ea8cb6ed1c988834a77f8916f6626bb2bc3eb75aee282a1c6"
    "c389e14a0fd7c62f1d945499c50908062fc1440f866ba766befaa4322980cd1aee50b5e0"
    "8b2b9512ed72c6aefbb35f762512b05a9716a697ac631afed91f82adffae311dcb1a7e54"
    "f688c099bd489fd1e3e3aed011009cbf6bb4c2816ddf"
)
TRANSACTION3 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(COINBASE1.id, 2),
            unlock_sig=unlock_sig_3,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=200_000_000, to_address=build_p2pkh(ADDRESS_4))],
    locktime=0,
)

# TRANSACTION 4
unlock_sig_4 = (
    "80657975be2c02556e31ce9b27e6f1ab2646bbfc87a1933878f32281de9790c9016d2be4"
    "23e362ef85aed1ab3e8cb61b30b22ce4401acfe1da8bb8498f5fdb560a8079b043fbab0a"
    "a455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585de"
    "bfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee"
)
TRANSACTION4 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(COINBASE2.id, 0),
            unlock_sig=unlock_sig_4,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=510_000, to_address=build_p2pkh(ADDRESS_5))],
    locktime=0,
)

# TRANSACTION 5
unlock_sig_5 = (
    "80030d8fcdadb846624a98a850e3a8a9b44dd347e7ebce2569c2aefbd7faa79e6aec8d3a"
    "b536f59e4177faccfd68bca2af4cda50b4e33ed1c3e9c6b1ad40e9dbc9805c440bc46d31"
    "6dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1eab11c4af165e4ce3eb06"
    "52f8d937620804fe15201c00a7466f56237810988db1"
)
TRANSACTION5 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(TRANSACTION2.id, 0),
            unlock_sig=unlock_sig_5,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=510_000, to_address=build_p2pkh(ADDRESS_4))],
    locktime=0,
)

# TRANSACTION 6
unlock_sig_6 = (
    "80b1eb302b6f5bbbd8b970800c63a1e8c285ab06fe7cfe0d3721969ac4707a7b31028c07"
    "676936144b9dc0ac71fc0edbefcc76dcaf7e61f5963e9da669eaa1aa7980f4b076bfcdb1"
    "f782018d2e3afa195ae1c92f18b3f97ba0ca1a9923bd48291817f8ba9a2dbe2fd347b5a7"
    "5998221022a548c9bfb326704c021870ccce90c6e1df"
)
TRANSACTION6 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(TRANSACTION3.id, 0),
            unlock_sig=unlock_sig_6,
            sequence=0,
        )
    ],
    txouts=[
        TxOut(value=110_000, to_address=build_p2pkh(ADDRESS_1)),
        TxOut(value=150_000, to_address=build_p2pkh(ADDRESS_2)),
        TxOut(value=50000, to_address=build_p2pkh(ADDRESS_3)),
        TxOut(value=175_000, to_address=build_p2pkh(ADDRESS_1)),
    ],
    locktime=0,
)

# TX 7: INVALID SIGNATURE
unlock_sig_7 = (
    "80078ab25c896a8cccc1b30c0ee9ca696b4b394d603bed3fed609f9b5a8fda49d55357b9"
    "330bcf1a8cfae5754bebad0cd98c82a8ccea7bd15158c382b3834ed5e78079b043fbab0a"
    "a455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585de"
    "bfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee"
)
TRANSACTION7 = Transaction(
    version=1,
    txins=[
        TxIn(
            to_spend=OutPoint(TRANSACTION5.id, 0),
            unlock_sig=unlock_sig_7,
            sequence=0,
        )
    ],
    txouts=[TxOut(value=110_000, to_address=build_p2pkh(ADDRESS_1))],
    locktime=0,
)
