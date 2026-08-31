from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1, WALLET_2


def _disable_pow(monkeypatch):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    monkeypatch.setattr("luracoin.pow.proof_of_work", lambda _block: 0)


def test_create_first_block(monkeypatch):
    """Block.create() initializes genesis, then mines height 1."""
    _disable_pow(monkeypatch)

    block = Block(miner=WALLET_1["address"])
    block.create()

    genesis = Block.get(0)
    assert block.height == 1
    assert block.prev_block_hash == genesis.id
    assert block.version == 1
    assert block.is_valid_proof()
    assert len(block.txns) >= 1
    assert block.txns[0].is_coinbase is True
    assert block.txns[0].value == mining_reward(1)
    assert block.txns[0].to_address == WALLET_1["address"]


def test_create_second_block(monkeypatch):
    """Consecutive create() calls link consecutive non-genesis blocks."""
    _disable_pow(monkeypatch)

    block0 = Block(miner=WALLET_1["address"])
    block0.create()

    block1 = Block(miner=WALLET_1["address"])
    block1.create()

    assert block1.height == 2
    assert block1.prev_block_hash == block0.id


def test_create_credits_miner_balance(monkeypatch):
    """After create(), miner should have mining reward in their account."""
    _disable_pow(monkeypatch)

    chain = Chain()
    block = Block(miner=WALLET_1["address"])
    block.create()

    account = chain.get_account(WALLET_1["address"])
    assert account is not None
    # WALLET_1 owns testnet genesis and receives exactly one block-1 reward.
    assert account["balance"] == Config.COINS_TO_FORGE + mining_reward(1)


def test_create_includes_fees_in_coinbase(monkeypatch):
    """Coinbase value should include mining_reward + sum of tx fees."""
    _disable_pow(monkeypatch)

    # First create a block so WALLET_1 has balance
    block0 = Block(miner=WALLET_1["address"])
    block0.create()

    chain = Chain()

    # Create a block with a fee-bearing transaction already in txns
    chain.set_account(WALLET_2["address"], {"balance": 10_000_000, "nonce": 0})
    tx = Transaction(
        chain=1,
        nonce=1,
        fee=5000,
        value=1000,
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
    assert coinbase.value == mining_reward(2) + 5000
