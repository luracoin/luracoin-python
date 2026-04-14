from binascii import unhexlify
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from luracoin.pow import proof_of_work
from tests.constants import WALLET_1, WALLET_2


def _make_valid_block(height=0, timestamp=1_623_168_442, prev_hash=None, txns=None):
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(height),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    all_txns = [coinbase] + (txns or [])
    block = Block(
        version=1, height=height, miner=WALLET_1["address"],
        prev_block_hash=prev_hash or "0" * 64,
        timestamp=timestamp, bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=all_txns,
    )
    proof_of_work(block)
    return block


def test_validate_block_with_no_saved_previous_still_validates():
    """Block at height > 0 with no saved previous block skips prev checks."""
    # This tests that validate() doesn't crash when prev block doesn't exist.
    # Block.get(height-1) returns None, so timestamp/height checks are skipped.
    block = _make_valid_block(height=5, timestamp=1_623_168_500)
    # Should still pass PoW and other checks
    assert block.validate() is True


def test_validate_rejects_block_with_invalid_transaction():
    """Block containing an invalid transaction should fail validation."""
    # Create a transaction with invalid fields (value=0)
    bad_tx = Transaction(
        chain=1, nonce=1, fee=100, value=0,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase, bad_tx],
    )
    proof_of_work(block)
    assert block.validate() is False


def test_validate_rejects_oversized_block():
    """Block exceeding max_block_size should fail validation."""
    # At height 0, max block size is 10_000 bytes.
    # Each tx is 213 bytes. Header ~118 bytes.
    # We need enough txns to exceed 10_000 bytes.
    # (10_000 - 118) / 213 ~ 46 txns max. So 50 should exceed.
    txns = []
    for i in range(50):
        tx = Transaction(
            chain=1, nonce=i, fee=0, value=1000 + i,
            from_address="0" * 34,
            to_address=WALLET_1["address"],
            unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
        )
        txns.append(tx)

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=txns,
    )
    proof_of_work(block)

    # Verify the block IS oversized
    from luracoin.chain import max_block_size
    assert len(block.serialize()) > max_block_size(0)

    assert block.validate() is False


def test_validate_coinbase_with_fees_is_valid():
    """Coinbase value = mining_reward + total_fees should pass."""
    chain = Chain()
    chain.set_account(WALLET_2["address"], {"balance": 10_000_000, "nonce": 0})

    fee_tx = Transaction(
        chain=1, nonce=1, fee=5000, value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )
    fee_tx = fee_tx.sign(unhexlify(WALLET_2["private_key"]))

    coinbase = Transaction(
        chain=1, nonce=0, fee=0,
        value=mining_reward(0) + 5000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase, fee_tx],
    )
    proof_of_work(block)
    assert block.validate() is True


def test_validate_coinbase_exceeding_reward_plus_fees_fails():
    """Coinbase value > mining_reward + total_fees should fail."""
    chain = Chain()
    chain.set_account(WALLET_2["address"], {"balance": 10_000_000, "nonce": 0})

    fee_tx = Transaction(
        chain=1, nonce=1, fee=5000, value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )
    fee_tx = fee_tx.sign(unhexlify(WALLET_2["private_key"]))

    coinbase = Transaction(
        chain=1, nonce=0, fee=0,
        value=mining_reward(0) + 5001,  # 1 lurashi too much
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase, fee_tx],
    )
    proof_of_work(block)
    assert block.validate() is False
