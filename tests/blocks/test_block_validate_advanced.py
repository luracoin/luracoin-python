import time
from unittest.mock import patch

from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def _make_valid_block(height=1, timestamp=None, prev_hash=None, txns=None):
    """Build a structurally valid regular block; tests control PoW."""
    previous = Block.get(height - 1)
    assert previous is not None
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=height,
        fee=0,
        value=mining_reward(height),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    all_txns = [coinbase] + (txns or [])

    block = Block(
        version=1, height=height, miner=WALLET_1["address"],
        prev_block_hash=prev_hash or previous.id,
        timestamp=timestamp or previous.timestamp + 1,
        bits=Block.expected_bits(height), nonce=0,
        txns=all_txns,
    )
    return block


def test_validate_rejects_future_timestamp():
    """Block timestamp too far in the future should fail."""
    initialize_chain()
    future_ts = int(time.time()) + Config.MAX_FUTURE_BLOCK_TIME + 100

    block = _make_valid_block(height=1, timestamp=future_ts)

    assert block.validate() is False


def test_validate_rejects_timestamp_before_previous():
    """Block timestamp <= previous block timestamp should fail."""
    block0 = initialize_chain()

    # Block 1 with timestamp BEFORE block 0
    block1 = _make_valid_block(
        height=1, timestamp=block0.timestamp - 1, prev_hash=block0.id
    )
    assert block1.validate() is False


def test_validate_accepts_timestamp_after_previous():
    """Block timestamp > previous block timestamp should pass."""
    block0 = initialize_chain()

    block1 = _make_valid_block(
        height=1, timestamp=block0.timestamp + 1, prev_hash=block0.id
    )
    with patch.object(Block, "is_valid_proof", return_value=True):
        assert block1.validate() is True


def test_validate_rejects_equal_timestamp():
    """Block timestamp == previous block timestamp should fail."""
    block0 = initialize_chain()

    block1 = _make_valid_block(
        height=1, timestamp=block0.timestamp, prev_hash=block0.id
    )
    assert block1.validate() is False
