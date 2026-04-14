import time
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from luracoin.pow import proof_of_work
from tests.constants import WALLET_1


def _make_valid_block(height=0, timestamp=None, prev_hash=None, txns=None):
    """Helper to build a valid block with easy PoW."""
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(height),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    all_txns = [coinbase] + (txns or [])

    block = Block(
        version=1, height=height, miner=WALLET_1["address"],
        prev_block_hash=prev_hash or "0" * 64,
        timestamp=timestamp or 1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=all_txns,
    )
    proof_of_work(block)
    return block


def test_validate_rejects_future_timestamp():
    """Block timestamp too far in the future should fail."""
    future_ts = int(time.time()) + Config.MAX_FUTURE_BLOCK_TIME + 100

    block = _make_valid_block(timestamp=future_ts)
    # Re-do PoW since timestamp changed the block id
    proof_of_work(block)

    assert block.validate() is False


def test_validate_rejects_timestamp_before_previous():
    """Block timestamp <= previous block timestamp should fail."""
    chain = Chain()

    block0 = _make_valid_block(height=0, timestamp=1_623_168_442)
    block0.save()

    # Block 1 with timestamp BEFORE block 0
    block1 = _make_valid_block(height=1, timestamp=1_623_168_441, prev_hash=block0.id)
    assert block1.validate() is False


def test_validate_accepts_timestamp_after_previous():
    """Block timestamp > previous block timestamp should pass."""
    chain = Chain()

    block0 = _make_valid_block(height=0, timestamp=1_623_168_442)
    block0.save()

    block1 = _make_valid_block(height=1, timestamp=1_623_168_443, prev_hash=block0.id)
    assert block1.validate() is True


def test_validate_rejects_equal_timestamp():
    """Block timestamp == previous block timestamp should fail."""
    chain = Chain()

    block0 = _make_valid_block(height=0, timestamp=1_623_168_442)
    block0.save()

    block1 = _make_valid_block(height=1, timestamp=1_623_168_442, prev_hash=block0.id)
    assert block1.validate() is False
