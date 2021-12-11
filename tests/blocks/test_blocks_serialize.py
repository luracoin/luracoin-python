import binascii
import json
from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from tests.helpers import add_test_transactions
from luracoin.config import Config
from tests.constants import WALLET_1


def test_block_serialize__with_one_transaction(blockchain):
    coinbase_transacion = Transaction(
        chain=1,
        nonce=8763,
        fee=100,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block1 = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
        txns=[coinbase_transacion],
    )

    block2 = Block().deserialize(block1.serialize())

    assert block1.id == block2.id
    assert block1.json() == block2.json()


def test_block_serialize__with_multiple_transaction():
    coinbase_transaction_1 = Transaction(
        chain=1,
        nonce=1,
        fee=0,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block1 = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
        txns=[coinbase_transaction_1],
    )

    transactions = add_test_transactions()

    coinbase_transaction_2 = Transaction(
        chain=1,
        nonce=2,
        fee=0,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block2 = Block(
        version=1,
        height=1,
        miner=WALLET_1["address"],
        prev_block_hash=block1.id,
        timestamp=1_623_208_442,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
        txns=[coinbase_transaction_2, *transactions],
    )

    block3 = Block().deserialize(block2.serialize())
    assert block2.id == block3.id
    assert block2.json() == block3.json()
