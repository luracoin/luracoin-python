import plyvel
import pytest
from luracoin.blocks import Block
from luracoin.chain import get_current_blk_file, serialise_block_to_save
from luracoin.config import Config
from luracoin.pow import proof_of_work
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


def test_blocks_validate_nonces():
    proof = proof_of_work(BLOCK1)
    assert BLOCK1.is_valid_proof
    assert proof == BLOCK1_VALID_NONCE
    assert BLOCK1.id == BLOCK1_ID

    proof = proof_of_work(BLOCK2)
    assert BLOCK2.is_valid_proof
    assert proof == BLOCK2_VALID_NONCE
    assert BLOCK2.id == BLOCK2_ID

    proof = proof_of_work(BLOCK3)
    assert BLOCK3.is_valid_proof
    assert proof == BLOCK3_VALID_NONCE
    assert BLOCK3.id == BLOCK3_ID

    proof = proof_of_work(BLOCK4)
    assert BLOCK4.is_valid_proof
    assert proof == BLOCK4_VALID_NONCE
    assert BLOCK4.id == BLOCK4_ID

    proof = proof_of_work(BLOCK5)
    assert BLOCK5.is_valid_proof
    assert proof == BLOCK5_VALID_NONCE
    assert BLOCK5.id == BLOCK5_ID

    proof = proof_of_work(BLOCK6)
    assert BLOCK6.is_valid_proof
    assert proof == BLOCK6_VALID_NONCE
    assert BLOCK6.id == BLOCK6_ID


def test_block_ids():
    assert BLOCK1.id == BLOCK1_ID
    assert BLOCK2.id == BLOCK2_ID
    assert BLOCK3.id == BLOCK3_ID
    assert BLOCK4.id == BLOCK4_ID
    assert BLOCK5.id == BLOCK5_ID
    assert BLOCK6.id == BLOCK6_ID


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
    assert block.nonce == BLOCK1.nonce
    assert block.prev_block_hash == BLOCK1.prev_block_hash
    assert [tx.id for tx in block.txns] == [tx.id for tx in BLOCK1.txns]
    assert block.id == BLOCK1.id

    block2 = Block()
    block2.deserialize(BLOCK2_SERIALISED)

    assert block2.version == BLOCK2.version
    assert block2.timestamp == BLOCK2.timestamp
    assert block2.bits == BLOCK2.bits
    assert block2.nonce == BLOCK2.nonce
    assert block2.prev_block_hash == BLOCK2.prev_block_hash
    assert [tx.id for tx in block2.txns] == [tx.id for tx in BLOCK2.txns]
    assert block2.id == BLOCK2.id

    block5 = Block()
    block5.deserialize(BLOCK5_SERIALISED)

    assert block5.version == BLOCK5.version
    assert block5.timestamp == BLOCK5.timestamp
    assert block5.bits == BLOCK5.bits
    assert block5.nonce == BLOCK5.nonce
    assert block5.prev_block_hash == BLOCK5.prev_block_hash
    assert sorted([tx.id for tx in block5.txns]) == sorted(
        [tx.id for tx in BLOCK5.txns]
    )
    assert block5.id == BLOCK5.id


def test_block_validate__pow(block1, block2):  # type: ignore
    assert block1.is_valid_proof is True
    assert block2.is_valid_proof is True


def test_block_validate(block1, block2):  # type: ignore
    assert block1.validate() is True
    assert block2.validate() is True


def test_block_save_into_disk(  # type: ignore
    blockchain, block1, block2, block3
):
    block1.save()

    f = open(Config.BLOCKS_DIR + get_current_blk_file(), "r")
    content = f.read()
    f.close()

    serialized_block1 = serialise_block_to_save(block1.serialize())
    assert content == serialized_block1

    block2.save()

    f = open(Config.BLOCKS_DIR + get_current_blk_file(), "r")
    content = f.read()
    f.close()

    serialized_block2 = serialise_block_to_save(block2.serialize())
    assert content == serialized_block1 + serialized_block2


def test_block_save_leveldb_keys(  # type: ignore
    blockchain, block1, block2, block3
):
    block1.save()
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    try:
        assert db.get(b"l") == b"000000"
        assert int(db.get(b"b")) == 1
        assert db.get(b"b1").decode() == "000000" + block1.id
        assert db.get(b"b" + block1.id.encode()).decode() == (
            "0100000000000000000000000000000000000000000000000000000000000000"
            "00000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e3683"
            "383489841e0fffffe4f98359182505000000010100000001"
        )
    finally:
        db.close()

    block2.save()
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    try:
        assert db.get(b"l") == b"000000"
        assert int(db.get(b"b")) == 2
        assert db.get(b"b2").decode() == "000000" + block2.id
        assert db.get(b"b" + block2.id.encode()).decode() == (
            "01000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e3683"
            "38348984000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5a"
            "b1f812451e0fffffe4f98359da1008000000020600000001"
        )
    finally:
        db.close()


def test_block_headers(blockchain, block1, block2, block3):  # type: ignore
    assert block1.header()["version"] == block1.version
    assert block1.header()["prev_block_hash"] == block1.prev_block_hash
    assert block1.header()["id"] == block1.id
    assert block1.header()["bits"] == block1.bits
    assert block1.header()["timestamp"] == block1.timestamp
    assert block1.header()["nonce"] == block1.nonce

    assert block2.header()["version"] == block2.version
    assert block2.header()["prev_block_hash"] == block2.prev_block_hash
    assert block2.header()["id"] == block2.id
    assert block2.header()["bits"] == block2.bits
    assert block2.header()["timestamp"] == block2.timestamp
    assert block2.header()["nonce"] == block2.nonce

    assert block3.header()["version"] == block3.version
    assert block3.header()["prev_block_hash"] == block3.prev_block_hash
    assert block3.header()["id"] == block3.id
    assert block3.header()["bits"] == block3.bits
    assert block3.header()["timestamp"] == block3.timestamp
    assert block3.header()["nonce"] == block3.nonce

    assert block1.header(serialised=True) == (
        "01000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e368338348984"
        "1e0fffffe4f98359182505000000"
    )
    assert block2.header(serialised=True) == (
        "01000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e36833834"
        "8984000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5ab1f81245"
        "1e0fffffe4f98359da1008000000"
    )
    assert block3.header(serialised=True) == (
        "01000000000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5ab1f8"
        "12454089c3d979b89975604d3c56a042589e1abd2307fa69e2fb56f68c7d9287ce09"
        "1e0fffffe4f98359789c1d000000"
    )


@pytest.mark.skip(reason="TODO")
def test_process_block_transactions_after_block_saved(  # type: ignore
    blockchain, block1, block2, block3
):
    block1.save()
    print("=====")
    block2.save()
    for tx in block2.txns:
        tx.save(2)

    db = plyvel.DB(Config.DATA_DIR + "chainstate", create_if_missing=True)
    for key, value in db:
        print(f"{key}: {value}")
    assert False
