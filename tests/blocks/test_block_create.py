from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1, WALLET_2


def test_create_first_block():
    """Block.create() should mine block 0 with coinbase."""
    # Use very easy difficulty so PoW is instant
    original_diff = Config.STARTING_DIFFICULTY
    Config.STARTING_DIFFICULTY = b"\x1f\x00\xff\xff"

    block = Block(miner=WALLET_1["address"])
    block.create()

    assert block.height == 0
    assert block.prev_block_hash == "0" * 64
    assert block.version == 1
    assert block.is_valid_proof()
    assert len(block.txns) >= 1
    assert block.txns[0].is_coinbase is True
    assert block.txns[0].value == mining_reward(0)
    assert block.txns[0].to_address == WALLET_1["address"]

    Config.STARTING_DIFFICULTY = original_diff


def test_create_second_block():
    """Block.create() for block 1 should reference block 0."""
    original_diff = Config.STARTING_DIFFICULTY
    Config.STARTING_DIFFICULTY = b"\x1f\x00\xff\xff"

    block0 = Block(miner=WALLET_1["address"])
    block0.create()

    block1 = Block(miner=WALLET_1["address"])
    block1.create()

    assert block1.height == 1
    assert block1.prev_block_hash == block0.id

    Config.STARTING_DIFFICULTY = original_diff


def test_create_credits_miner_balance():
    """After create(), miner should have mining reward in their account."""
    original_diff = Config.STARTING_DIFFICULTY
    Config.STARTING_DIFFICULTY = b"\x1f\x00\xff\xff"

    chain = Chain()
    block = Block(miner=WALLET_1["address"])
    block.create()

    account = chain.get_account(WALLET_1["address"])
    assert account is not None
    # Miner gets: coinbase tx value + mining reward from save()
    assert account["balance"] >= mining_reward(0)

    Config.STARTING_DIFFICULTY = original_diff


def test_create_includes_fees_in_coinbase():
    """Coinbase value should include mining_reward + sum of tx fees."""
    original_diff = Config.STARTING_DIFFICULTY
    Config.STARTING_DIFFICULTY = b"\x1f\x00\xff\xff"

    # First create a block so WALLET_1 has balance
    block0 = Block(miner=WALLET_1["address"])
    block0.create()

    chain = Chain()

    # Create a block with a fee-bearing transaction already in txns
    chain.set_account(WALLET_2["address"], {"balance": 10_000_000, "nonce": 0})
    tx = Transaction(
        chain=1, nonce=1, fee=5000, value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    )
    from binascii import unhexlify
    tx = tx.sign(unhexlify(WALLET_2["private_key"]))

    block1 = Block(miner=WALLET_1["address"], txns=[tx])
    block1.create()

    # First tx should be coinbase with reward + fees
    coinbase = block1.txns[0]
    assert coinbase.is_coinbase
    assert coinbase.value == mining_reward(1) + 5000

    Config.STARTING_DIFFICULTY = original_diff
