from luracoin.config import Config
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def test_block_validate_rejects_excess_coinbase():
    """Coinbase value exceeding reward + fees should fail validation."""
    coinbase = Transaction(
        chain=1, nonce=0, fee=0,
        value=999_999_999_999,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    assert block.validate() is False


def test_block_validate_accepts_valid_coinbase():
    """Coinbase with exactly mining_reward should pass after PoW."""
    from luracoin.pow import proof_of_work

    reward = mining_reward(0)

    coinbase = Transaction(
        chain=1, nonce=0, fee=0,
        value=reward,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    proof_of_work(block)
    assert block.validate() is True


def test_block_save_credits_miner():
    """Block.save() should credit mining reward to miner's account."""
    chain = Chain()

    coinbase = Transaction(
        chain=1, nonce=0, fee=0,
        value=mining_reward(0),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    block.save()

    account = chain.get_account(WALLET_1["address"])
    # Miner gets: coinbase value + mining reward
    expected = mining_reward(0) + mining_reward(0)
    assert account["balance"] == expected
