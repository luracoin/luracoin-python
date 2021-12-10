import binascii
import json
from binascii import unhexlify
from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from tests.helpers import add_test_transactions
from luracoin.config import Config
from luracoin.pow import proof_of_work
from luracoin.chain import Chain
from tests.constants import WALLET_1


def test_full_blockchain():
    START_TIMESTAMP = 1639159886
    chain = Chain()
    assert chain.height == 0

    block1 = Block(
        version=1,
        height=0,
        prev_block_hash="0" * 64,
        miner=WALLET_1["address"],
        timestamp=START_TIMESTAMP,
        bits=Config.STARTING_DIFFICULTY,
        nonce=156369,
        txns=[],
    )
    print(json.dumps(block1.json(), indent=4))

    chain.add_block(block1)
    assert chain.height == 0
    # TODO: Check miner balance
    # TODO: Check file content
    # TODO: Check stacking

    # Transaction to stack 15 Luracoins
    transaction_1 = Transaction(
        chain=1,
        nonce=1,
        fee=0,
        value=Config.LURASHIS_PER_COIN * 15,
        to_address=Config.STAKING_ADDRESS,
    )

    transaction_1.sign(unhexlify(WALLET_1["private_key"]))
    assert transaction_1.validate() == True

    block2 = Block(
        version=1,
        height=1,
        prev_block_hash=block1.id,
        miner=WALLET_1["address"],
        timestamp=START_TIMESTAMP + (3*60),  # 3 minutes
        bits=Config.STARTING_DIFFICULTY,
        nonce=4358788,
        txns=[transaction_1],
    )
    print(json.dumps(block2.json(), indent=4))

    chain.add_block(block2)
    assert chain.height == 1
    # TODO: Check miner balance
    # TODO: Check file content
    # TODO: Check stacking

    assert False
