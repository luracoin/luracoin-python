from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.helpers import mining_reward
from luracoin.pow import proof_of_work


def test_validate_pow_required():
    """Block with nonce=0 and hard difficulty should fail PoW check."""
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1d\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    # Very unlikely nonce=0 solves this difficulty
    assert block.is_valid_proof() is False


def test_validate_with_easy_difficulty():
    """Block with easy difficulty should validate after PoW."""
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    proof_of_work(block)
    assert block.validate() is True


def test_validate_rejects_oversized_coinbase():
    """Coinbase exceeding mining reward should fail."""
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0) + 1,
        from_address="0" * 34,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    assert block.validate() is False
