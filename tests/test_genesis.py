from luracoin.genesis import build_genesis_block, initialize_chain, GENESIS_ADDRESS, GENESIS_TIMESTAMP
from luracoin.config import Config
from luracoin.chain import Chain


def test_build_genesis_block_height_zero():
    block = build_genesis_block()
    assert block.height == 0


def test_build_genesis_block_prev_hash_is_zeros():
    block = build_genesis_block()
    assert block.prev_block_hash == "0" * 64


def test_build_genesis_block_miner_is_genesis_address():
    block = build_genesis_block()
    assert block.miner == GENESIS_ADDRESS


def test_build_genesis_block_timestamp():
    block = build_genesis_block()
    assert block.timestamp == GENESIS_TIMESTAMP


def test_build_genesis_block_coinbase_value_is_coins_to_forge():
    block = build_genesis_block()
    assert len(block.txns) == 1
    assert block.txns[0].is_coinbase is True
    assert block.txns[0].value == Config.COINS_TO_FORGE


def test_build_genesis_block_coinbase_to_address():
    block = build_genesis_block()
    assert block.txns[0].to_address == GENESIS_ADDRESS


def test_initialize_chain_saves_genesis():
    chain = Chain()
    assert chain.get_block_file_number(0) is None

    initialize_chain()

    assert chain.get_block_file_number(0) is not None
    assert chain.tip == 0


def test_initialize_chain_is_idempotent():
    chain = Chain()
    initialize_chain()
    tip_after_first = chain.tip
    file_number_first = chain.get_block_file_number(0)

    initialize_chain()
    assert chain.tip == tip_after_first
    assert chain.get_block_file_number(0) == file_number_first
