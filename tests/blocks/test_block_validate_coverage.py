from binascii import unhexlify

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.transactions import Transaction
from tests.constants import WALLET_1, WALLET_2


def _make_next_block(txns=None, coinbase_value=None):
    genesis = initialize_chain()
    regular_txns = txns or []
    fees = sum(transaction.fee for transaction in regular_txns)
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=(
            mining_reward(1) + fees
            if coinbase_value is None
            else coinbase_value
        ),
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
        txns=[coinbase] + regular_txns,
    )


def test_validate_block_with_no_saved_previous_is_rejected():
    """Consensus fails closed when its required predecessor is absent."""
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=5,
        fee=0,
        value=mining_reward(5),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=5,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_500,
        bits=Config.STARTING_DIFFICULTY,
        nonce=0,
        txns=[coinbase],
    )

    assert block.validate() is False


def test_validate_rejects_block_with_invalid_transaction(monkeypatch):
    """Block containing a signed transaction with value zero is invalid."""
    bad_tx = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=100,
        value=0,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(unhexlify(WALLET_1["private_key"]))
    block = _make_next_block([bad_tx])
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is False


def test_validate_rejects_oversized_block(monkeypatch):
    """The active size limit is enforced independently of other rules."""
    block = _make_next_block()
    artificial_limit = len(block.serialize()) - 1
    monkeypatch.setattr(
        "luracoin.blocks.max_block_size", lambda _height: artificial_limit
    )
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert len(block.serialize()) > artificial_limit
    assert block.validate() is False


def test_validate_coinbase_with_fees_is_valid(monkeypatch):
    """Coinbase value equal to the height subsidy plus fees is valid."""
    chain = Chain()
    chain.set_account(
        WALLET_2["address"], {"balance": 10_000_000, "nonce": 0}
    )
    fee_tx = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=5000,
        value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    ).sign(unhexlify(WALLET_2["private_key"]))
    block = _make_next_block([fee_tx])
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.txns[0].value == mining_reward(1) + fee_tx.fee
    assert block.validate() is True


def test_validate_coinbase_exceeding_reward_plus_fees_fails(monkeypatch):
    """A coinbase one lurashi above subsidy plus fees is rejected."""
    chain = Chain()
    chain.set_account(
        WALLET_2["address"], {"balance": 10_000_000, "nonce": 0}
    )
    fee_tx = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=5000,
        value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    ).sign(unhexlify(WALLET_2["private_key"]))
    block = _make_next_block(
        [fee_tx], coinbase_value=mining_reward(1) + fee_tx.fee + 1
    )
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)

    assert block.validate() is False
