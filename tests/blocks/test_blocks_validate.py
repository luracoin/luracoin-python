from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.transactions import Transaction
from tests.constants import WALLET_1


def _next_block(coinbase_value):
    genesis = initialize_chain()
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=coinbase_value,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    return Block(
        version=1,
        height=1,
        miner=WALLET_1["address"],
        prev_block_hash=genesis.id,
        timestamp=genesis.timestamp + 1,
        bits=Block.expected_bits(1),
        nonce=0,
        txns=[coinbase],
    )


def test_validate_pow_required():
    """A nonce that misses a hard target does not satisfy proof of work."""
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
        prev_block_hash="0" * 64,
        timestamp=1_623_168_443,
        bits=b"\x1d\x00\xff\xff",
        nonce=0,
        txns=[coinbase],
    )

    assert block.is_valid_proof() is False


def test_validate_with_expected_difficulty(monkeypatch):
    """A regular block satisfying the active target validates."""
    block = _next_block(mining_reward(1))
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is True


def test_validate_rejects_oversized_coinbase(monkeypatch):
    """Coinbase exceeding the height subsidy is rejected."""
    block = _next_block(mining_reward(1) + 1)
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is False
