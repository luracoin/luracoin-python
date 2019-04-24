from typing import Generator

from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.chain import (
    get_current_file_number,
    get_current_file_name,
    serialise_block_to_save,
    next_blk_file,
    get_current_blk_file,
)


def test_get_current_file_number(blockchain) -> None:  # type: ignore
    assert get_current_file_number() == "000000"


def test_get_current_file_name() -> None:
    assert get_current_file_name("000000") == "blk000000.dat"
    assert get_current_file_name("000001") == "blk000001.dat"
    assert get_current_file_name("021056") == "blk021056.dat"


def test_serialise_block_to_save() -> None:
    serialised_block = (
        "ba77d89f010000000000000000000000000000000000000000000000000000000000"
        "000000000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721ad14e3683"
        "383489841e0fffffe4f9835918250500000001010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff0100000000003005ed0b"
        "2000000003476a91500ff7ff008512170c57980f447dc24f5c52e2df03c88ac002f6"
        "859000000003476a915003ea6275ba0c6860ce74727f72617883099961a4388ac006"
        "5cd1d000000003476a91500785211d22e8c5c6bad7410b9baf99dac866a447f88ac"
    )

    block = Block()
    block.deserialize(serialised_block)

    actual = serialise_block_to_save(serialised_block)
    expected = (
        "ba77d89fd30100000100000000000000000000000000000000000000000000000000"
        "00000000000000000000000000c88505d2ddb65ad8300cda93a69bb19c8ab6fa721a"
        "d14e3683383489841e0fffffe4f98359182505000000010100010000000000000000"
        "000000000000000000000000000000000000000000000000ffffffff010000000000"
        "3005ed0b2000000003476a91500ff7ff008512170c57980f447dc24f5c52e2df03c8"
        "8ac002f6859000000003476a915003ea6275ba0c6860ce74727f72617883099961a4"
        "388ac0065cd1d000000003476a91500785211d22e8c5c6bad7410b9baf99dac866a4"
        "47f88ac"
    )

    # Ignore the block length to check if the block saved still the same.
    block_read_from_file = Block()
    block_read_from_file.deserialize(actual[:8] + actual[16:])

    assert actual == expected
    assert serialised_block == actual[:8] + actual[16:]
    assert block.version == block_read_from_file.version
    assert block.timestamp == block_read_from_file.timestamp
    assert block.bits == block_read_from_file.bits
    assert block.nonce == block_read_from_file.nonce
    assert block.prev_block_hash == block_read_from_file.prev_block_hash
    assert [tx.id for tx in block.txns] == [
        tx.id for tx in block_read_from_file.txns
    ]
    assert block.id == block_read_from_file.id


def test_next_blk_file() -> None:
    assert next_blk_file("000001") == "000002"
    assert next_blk_file("000210") == "000211"
    assert next_blk_file("999998") == "999999"


def test_blk_file_number_increase_when_file_surpases_the_max_size_allowed(
    blockchain: Generator
) -> None:
    Config.MAX_FILE_SIZE = 2000  # Override the max file size for the test

    current_file = get_current_blk_file()
    current_file_number = get_current_file_number()

    assert current_file_number == "000000"

    path = f"{Config.BLOCKS_DIR}{current_file}"
    content_length = Config.MAX_FILE_SIZE + 100  # Surpass

    f = open(path, "a")
    f.write("".join("x" for _ in range(content_length)))
    f.close()

    actual_file_number = get_current_file_number()

    assert actual_file_number == "000001"
