import plyvel
import pytest
from luracoin.blocks import Block
from luracoin.chain import get_current_blk_file, serialise_block_to_save
from luracoin.config import Config
from luracoin.pow import proof_of_work
from tests.transactions.constants import COINBASE1
from tests.blocks.constants import (
    BLOCK1,
    BLOCK1_ID,
    BLOCK1_VALID_NONCE,
    BLOCK1_SERIALISED,
    BLOCK2,
    BLOCK2_ID,
    BLOCK2_VALID_NONCE,
    BLOCK2_SERIALISED,
    BLOCK3,
    BLOCK3_ID,
    BLOCK3_VALID_NONCE,
    BLOCK3_SERIALISED,
    BLOCK4,
    BLOCK4_ID,
    BLOCK4_VALID_NONCE,
    BLOCK4_SERIALISED,
    BLOCK5,
    BLOCK5_ID,
    BLOCK5_VALID_NONCE,
    BLOCK5_SERIALISED,
    BLOCK6,
    BLOCK6_ID,
    BLOCK6_VALID_NONCE,
    BLOCK6_SERIALISED,
)


def test_block_serialize():
    assert BLOCK1.serialize() == BLOCK1_SERIALISED
    assert BLOCK2.serialize() == BLOCK2_SERIALISED
    assert BLOCK3.serialize() == BLOCK3_SERIALISED
    assert BLOCK4.serialize() == BLOCK4_SERIALISED
    assert BLOCK5.serialize() == BLOCK5_SERIALISED
    assert BLOCK6.serialize() == BLOCK6_SERIALISED


def test_block_deserialize(block1, block2):  # type: ignore
    block = Block()
    block.deserialize(BLOCK1_SERIALISED)

    assert block.version == BLOCK1.version
    assert block.timestamp == BLOCK1.timestamp
    assert block.bits == BLOCK1.bits
    assert block.prev_block_hash == BLOCK1.prev_block_hash
    assert [tx.id for tx in block.txns] == [tx.id for tx in BLOCK1.txns]
    assert block.id == BLOCK1.id

    block2 = Block()
    block2.deserialize(BLOCK2_SERIALISED)

    assert block2.version == BLOCK2.version
    assert block2.timestamp == BLOCK2.timestamp
    assert block2.bits == BLOCK2.bits
    assert block2.prev_block_hash == BLOCK2.prev_block_hash
    assert [tx.id for tx in block2.txns] == [tx.id for tx in BLOCK2.txns]
    assert block2.id == BLOCK2.id

    block3 = Block()
    block3.deserialize(BLOCK3_SERIALISED)

    assert block3.version == BLOCK3.version
    assert block3.timestamp == BLOCK3.timestamp
    assert block3.bits == BLOCK3.bits
    assert block3.prev_block_hash == BLOCK3.prev_block_hash
    assert [tx.id for tx in block3.txns] == [tx.id for tx in BLOCK3.txns]
    assert block3.id == BLOCK3.id

    block4 = Block()
    block4.deserialize(BLOCK4_SERIALISED)

    assert block4.version == BLOCK4.version
    assert block4.timestamp == BLOCK4.timestamp
    assert block4.bits == BLOCK4.bits
    assert block4.prev_block_hash == BLOCK4.prev_block_hash
    assert [tx.id for tx in block4.txns] == [tx.id for tx in BLOCK4.txns]
    assert block4.id == BLOCK4.id

    block5 = Block()
    block5.deserialize(BLOCK5_SERIALISED)

    assert block5.version == BLOCK5.version
    assert block5.timestamp == BLOCK5.timestamp
    assert block5.bits == BLOCK5.bits
    assert block5.prev_block_hash == BLOCK5.prev_block_hash
    assert [tx.id for tx in block5.txns] == [tx.id for tx in BLOCK5.txns]
    assert block5.id == BLOCK5.id
