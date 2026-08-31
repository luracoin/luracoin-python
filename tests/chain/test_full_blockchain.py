from binascii import unhexlify

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.transactions import Transaction
from tests.constants import WALLET_1, WALLET_2


def test_full_blockchain(monkeypatch):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    chain = Chain()
    genesis = initialize_chain()

    assert chain.tip == 0
    assert chain.get_block_file_number(0) == 0
    assert len(Block.get_blocks_from_file(0)) == 1
    assert Block.get(0).serialize() == genesis.serialize()

    amount = Config.LURASHIS_PER_COIN * 15
    transaction = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=amount,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(unhexlify(WALLET_1["private_key"]))
    assert transaction.validate() is True

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
        prev_block_hash=genesis.id,
        miner=WALLET_1["address"],
        timestamp=genesis.timestamp + Config.BLOCK_TIME,
        bits=Block.expected_bits(1),
        nonce=0,
        txns=[coinbase, transaction],
    )
    block.save()

    assert chain.tip == 1
    assert chain.get_block_file_number(1) == 0
    assert len(Block.get_blocks_from_file(0)) == 2
    assert Block.get(1).serialize() == block.serialize()
    assert chain.get_account(WALLET_2["address"])["balance"] == amount
    assert chain.get_account(WALLET_1["address"])["nonce"] == 1
    assert chain.get_account(WALLET_1["address"])["balance"] == (
        Config.COINS_TO_FORGE - amount + mining_reward(1)
    )
