from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def test_block_get_returns_none_when_file_has_no_matching_height():
    """Block.get() returns None when block index points to a file
    that doesn't contain the requested height."""
    chain = Chain()

    # Save a block at height 0
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )
    block.save()

    # Manually set block file number for height 999 to file 0
    # File 0 only contains block at height 0, not 999
    chain.set_block_file_number(999, 0)

    result = Block.get(999)
    assert result is None
