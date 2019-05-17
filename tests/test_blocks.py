import plyvel
from luracoin.blocks import Block
from luracoin.chain import get_current_blk_file, serialise_block_to_save
from luracoin.config import Config


def test_block_ids(block1, block2):  # type: ignore
    assert block1.id == (
        "000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e368338348984"
    )

    assert block2.id == (
        "000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5ab1f81245"
    )


def test_block_serialize(block1, block2):  # type: ignore
    assert block1.serialize() == (
        "ba77d89f010000000000000000000000000000000000000000000000000000000000"
        "000000000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e3683"
        "383489841e0fffffe4f9835918250500000001010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff0100000000003005ed0b"
        "2000000003476a91500ff7ff008512170c57980f447dc24f5c52e2df03c88ac002f6"
        "859000000003476a915003ea6275ba0c6860ce74727f72617883099961a4388ac006"
        "5cd1d000000003476a91500785211d22e8c5c6bad7410b9baf99dac866a447f88ac"
    )

    assert block2.serialize() == (
        "ba77d89f01000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e"
        "368338348984000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5a"
        "b1f812451e0fffffe4f98359da100800000006010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff011000000000100f2052"
        "a010000003476a915008d3f74c5f4b7b9d3193a950986a9a16decb4155088ac01000"
        "14ac727f587761a17f5a3b63de589959989c655b579d261361ebaa287954440a5000"
        "000000100000000001d0090000000000003476a915002fb168b47d7cb54b07c7a4c4"
        "f7c005811f0a775d88ac0100014ac727f587761a17f5a3b63de589959989c655b579"
        "d261361ebaa287954440a500000000010000000000180969800000000003476a9150"
        "0d00b433df737fd3da4b2551a356d556206f2e60788ac0100014ac727f587761a17f"
        "5a3b63de589959989c655b579d261361ebaa287954440a5000000000100000000001"
        "00c2eb0b000000003476a915002a35a40188d3ca15da2cb5ac43c5f3add8c64b1688"
        "ac0100014ac727f587761a17f5a3b63de589959989c655b579d261361ebaa2879544"
        "40a500000000010000000000130c80700000000003476a91500785211d22e8c5c6ba"
        "d7410b9baf99dac866a447f88ac0100014ac727f587761a17f5a3b63de589959989c"
        "655b579d261361ebaa287954440a501000000010000000000130c807000000000034"
        "76a9150044d27de0e2f8e87f26beaf3cc727f1a642a09af388ac"
    )


def test_block_deserialize(block1, block2):  # type: ignore
    block = Block()

    block.deserialize(
        "ba77d89f01000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e"
        "368338348984000003702a732e82a86303552b0c056bfcbd410447af85065ed7fe5a"
        "b1f812451e0fffffe4f98359da100800000006010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff011000000000100f2052"
        "a010000003476a915008d3f74c5f4b7b9d3193a950986a9a16decb4155088ac01000"
        "14ac727f587761a17f5a3b63de589959989c655b579d261361ebaa287954440a5000"
        "000000100000000001d0090000000000003476a915002fb168b47d7cb54b07c7a4c4"
        "f7c005811f0a775d88ac0100014ac727f587761a17f5a3b63de589959989c655b579"
        "d261361ebaa287954440a500000000010000000000180969800000000003476a9150"
        "0d00b433df737fd3da4b2551a356d556206f2e60788ac0100014ac727f587761a17f"
        "5a3b63de589959989c655b579d261361ebaa287954440a5000000000100000000001"
        "00c2eb0b000000003476a915002a35a40188d3ca15da2cb5ac43c5f3add8c64b1688"
        "ac0100014ac727f587761a17f5a3b63de589959989c655b579d261361ebaa2879544"
        "40a500000000010000000000130c80700000000003476a91500785211d22e8c5c6ba"
        "d7410b9baf99dac866a447f88ac0100014ac727f587761a17f5a3b63de589959989c"
        "655b579d261361ebaa287954440a501000000010000000000130c807000000000034"
        "76a9150044d27de0e2f8e87f26beaf3cc727f1a642a09af388ac"
    )

    assert block.version == block2.version
    assert block.timestamp == block2.timestamp
    assert block.bits == block2.bits
    assert block.nonce == block2.nonce
    assert block.prev_block_hash == block2.prev_block_hash
    assert [tx.id for tx in block.txns] == [tx.id for tx in block2.txns]
    assert block.id == block2.id

    block_small = Block()
    block_small.deserialize(
        "ba77d89f010000000000000000000000000000000000000000000000000000000000"
        "000000000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e3683"
        "383489841e0fffffe4f9835918250500000001010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff0100000000003005ed0b"
        "2000000003476a91500ff7ff008512170c57980f447dc24f5c52e2df03c88ac002f6"
        "859000000003476a915003ea6275ba0c6860ce74727f72617883099961a4388ac006"
        "5cd1d000000003476a91500785211d22e8c5c6bad7410b9baf99dac866a447f88ac"
    )

    assert block_small.version == block1.version
    assert block_small.timestamp == block1.timestamp
    assert block_small.bits == block1.bits
    assert block_small.nonce == block1.nonce
    assert block_small.prev_block_hash == block1.prev_block_hash
    assert [tx.id for tx in block_small.txns] == [tx.id for tx in block1.txns]
    assert block_small.id == block1.id


def test_block_validate__pow(block1, block2):  # type: ignore
    assert block1.is_valid_proof is True
    assert block2.is_valid_proof is True


def test_block_validate(block1, block2):  # type: ignore
    assert block1.validate() is True
    assert block2.validate() is True


def test_block_save_into_disk(
    blockchain, block1, block2, block3
):  # type: ignore
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


def test_block_save_leveldb_keys(
    blockchain, block1, block2, block3
):  # type: ignore
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
