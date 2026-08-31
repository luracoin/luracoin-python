from unittest.mock import patch

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.transactions import Transaction
from tests.constants import WALLET_1


def test_block_save():
    genesis = initialize_chain()
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=mining_reward(1),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=1,
        miner=WALLET_1["address"],
        prev_block_hash=genesis.id,
        timestamp=genesis.timestamp + 1,
        bits=Block.expected_bits(1),
        nonce=0,
        txns=[coinbase],
    )

    chain = Chain()
    assert chain.tip == 0
    with patch.object(Block, "is_valid_proof", return_value=True):
        block.save()

    assert chain.tip == 1
    assert chain.get_block_file_number(1) == 0
    persisted = Block.get(1)
    assert persisted is not None
    assert persisted.serialize() == block.serialize()
