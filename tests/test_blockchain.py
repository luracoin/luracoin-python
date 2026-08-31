from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.transactions import Transaction
from tests.constants import WALLET_1, WALLET_2


def _next_block(miner, coinbase_value):
    genesis = initialize_chain()
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=coinbase_value,
        from_address="0" * 34,
        to_address=miner,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    return Block(
        version=1,
        height=1,
        miner=miner,
        prev_block_hash=genesis.id,
        timestamp=genesis.timestamp + 1,
        bits=Block.expected_bits(1),
        nonce=0,
        txns=[coinbase],
    )


def test_block_validate_rejects_excess_coinbase(monkeypatch):
    """Coinbase value exceeding reward plus fees fails validation."""
    block = _next_block(WALLET_1["address"], 999_999_999_999)
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is False


def test_block_validate_accepts_valid_coinbase(monkeypatch):
    """Coinbase with exactly the height subsidy passes validation."""
    block = _next_block(WALLET_1["address"], mining_reward(1))
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is True


def test_block_save_credits_miner_once(monkeypatch):
    """Block.save() credits exactly the single coinbase output."""
    block = _next_block(WALLET_2["address"], mining_reward(1))
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    block.save()

    account = Chain().get_account(WALLET_2["address"])
    assert account == {"balance": mining_reward(1), "nonce": 0}
