import binascii
import json
from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from tests.helpers import add_test_transactions
from luracoin.config import Config
from luracoin.pow import proof_of_work
from luracoin.chain import Chain
from tests.constants import WALLET_1


def test_block_save():
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
        bits=b"\x1d\x0f\xff\xff",
        nonce=12308683,
        txns=[coinbase_transaction_1],
    )

    print(block1.json())

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
        timestamp=1_623_168_442,
        bits=b"\x1d\x0f\xff\xff",
        nonce=12308683,
        txns=[coinbase_transaction_2],
    )

    print(block2.json())

    chain = Chain()
    assert chain.tip == 0
    block1.save()
    assert chain.tip == 0
    block2.save()
    assert chain.tip == 1

    assert False
