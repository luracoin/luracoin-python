import pytest
from luracoin.config import Config
from luracoin.chain import (
    next_blk_file,
    get_blk_file_size,
    get_current_blk_file,
    Chain,
)


def test_next_blk_file() -> None:
    assert next_blk_file("000001") == "000002"
    assert next_blk_file("000210") == "000211"
    assert next_blk_file("999998") == "999999"


def test_chain_height():
    chain = Chain()
    assert chain.height == 0
    chain.set_height(chain.height + 1)
    assert chain.height == 1
    chain.set_height(chain.height + 1)
    assert chain.height == 2
    chain.set_height(9999999)
    assert chain.height == 9999999


def test_chain_current_file_number() -> None:
    chain = Chain()
    assert chain.current_file_number == 0
    chain.set_current_file_number(chain.current_file_number + 1)
    assert chain.current_file_number == 1
    chain.set_current_file_number(chain.current_file_number + 1)
    assert chain.current_file_number == 2
    chain.set_current_file_number(9999999)
    assert chain.current_file_number == 9999999


def test_block_file_numbers() -> None:
    chain = Chain()
    assert chain.get_block_file_number(100) == None
    chain.set_block_file_number(100, 1)
    assert chain.get_block_file_number(100) == 1
    chain.set_block_file_number(100, 10)
    chain.set_block_file_number(653020, 250)
    assert chain.get_block_file_number(100) == 10
    assert chain.get_block_file_number(653020) == 250


def test_accounts() -> None:
    chain = Chain()
    assert chain.get_account("LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx") == None
    chain.set_account("LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx", {"balance": 100})
    assert chain.get_account("LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx") == {
        "balance": 100
    }
    chain.set_account(
        "LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx",
        {"balance": 100, "committed": 5000},
    )
    assert chain.get_account("LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx") == {
        "balance": 100,
        "committed": 5000,
    }
    chain.set_account(
        "LXs5GsdMxWtCcXZ4RhZHdKpLs7c71q18eM",
        {"balance": 0, "committed": 10000},
    )
    assert chain.get_account("LXs5GsdMxWtCcXZ4RhZHdKpLs7c71q18eM") == {
        "balance": 0,
        "committed": 10000,
    }


def test_chain_current_file_number_increase_when_file_surpases_the_max_size_allowed() -> None:
    chain = Chain()
    Config.MAX_FILE_SIZE = 1000  # Override the max file size for the test

    current_file = get_current_blk_file()
    print(current_file)
    current_file_number = chain.current_file_number

    assert current_file_number == 0

    path = f"{Config.BLOCKS_DIR}{current_file}"
    content_length = Config.MAX_FILE_SIZE + 100  # Surpass

    f = open(path, "a")
    f.write("".join("x" for _ in range(content_length)))
    f.close()

    actual_file_number = chain.current_file_number

    assert actual_file_number == 1


def test_get_blk_file_size() -> None:
    chain = Chain()
    Config.MAX_FILE_SIZE = 1000  # Override the max file size for the test

    path = f"{Config.BLOCKS_DIR}testblock"

    f = open(path, "a")
    f.write("".join("x" for _ in range(100)))
    f.close()

    assert get_blk_file_size("testblock") == 100
