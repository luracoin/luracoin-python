import pytest
from unittest.mock import patch, call
from luracoin.config import Config
from luracoin.chain import (
    next_blk_file,
    get_blk_file_size,
    get_current_blk_file,
    open_database,
    set_value,
    Chain,
)


def test_next_blk_file() -> None:
    assert next_blk_file("000001") == "000002"
    assert next_blk_file("000210") == "000211"
    assert next_blk_file("999998") == "999999"


def test_chain_height():
    chain = Chain()
    assert chain.tip == 0
    chain.set_tip(chain.tip + 1)
    assert chain.tip == 1
    chain.set_tip(chain.tip + 1)
    assert chain.tip == 2
    chain.set_tip(9999999)
    assert chain.tip == 9999999


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


def test_transaction_location_validates_and_decodes_index() -> None:
    transaction_id = "ab" * 32
    set_value(
        Config.DATABASE_CHAINSTATE,
        b"t" + transaction_id.encode(),
        (123).to_bytes(4, "little") + (7).to_bytes(2, "little"),
    )

    chain = Chain()
    assert chain.get_transaction_location(transaction_id.upper()) == (123, 7)
    assert chain.get_transaction_location("not-a-hash") is None
    assert chain.get_transaction_location("ff" * 32) is None


def test_versioned_block_location_round_trip_and_legacy_compatibility() -> (
    None
):
    chain = Chain()
    chain.set_block_location(7, 3, 1234, 331)

    assert chain.get_block_location(7) == (3, 1234, 331)
    assert chain.get_block_file_number(7) == 3

    chain.set_block_file_number(7, 4)
    assert chain.get_block_location(7) == (4, None, None)
    assert chain.get_block_file_number(7) == 4


def test_block_location_rejects_out_of_range_values() -> None:
    chain = Chain()

    with pytest.raises(ValueError, match="height"):
        chain.set_block_location(-1, 0, 0, 331)
    with pytest.raises(ValueError, match="file number"):
        chain.set_block_location(0, -1, 0, 331)
    with pytest.raises(ValueError, match="offset"):
        chain.set_block_location(0, 0, -1, 331)
    with pytest.raises(ValueError, match="length"):
        chain.set_block_location(0, 0, 0, 1)


def test_block_location_rejects_unknown_or_malformed_stored_values() -> None:
    height = 7
    key = height.to_bytes(4, byteorder="little", signed=False)

    set_value(Config.DATABASE_BLOCKS, key, b"\x02" + b"\x00" * 16)
    with pytest.raises(ValueError, match="unsupported"):
        Chain().get_block_location(height)

    set_value(Config.DATABASE_BLOCKS, key, b"\x01\x00")
    with pytest.raises(ValueError, match="unsupported"):
        Chain().get_block_location(height)


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


def test_chain_current_file_number_increase_when_file_surpases_the_max_size_allowed() -> (
    None
):
    chain = Chain()
    Config.MAX_FILE_SIZE = 1000  # Override the max file size for the test

    current_file_number = chain.current_file_number
    current_file = get_current_blk_file(current_file_number)

    assert current_file_number == 0

    path = f"{Config.BLOCKS_DIR}{current_file}"
    content_length = Config.MAX_FILE_SIZE + 100  # Surpass

    f = open(path, "a")
    f.write("".join("x" for _ in range(content_length)))
    f.close()

    actual_file_number = chain.current_file_number

    assert actual_file_number == 1


def test_database_name_always_string():
    """
    Bug 1.3: set_tip/tip pass database_name.encode() (bytes) while other
    methods pass database_name as string. open_database expects a string.
    All calls must pass strings.
    """
    chain = Chain()

    with patch(
        "luracoin.chain.open_database", wraps=open_database
    ) as mock_open:
        chain.set_tip(5)
        for c in mock_open.call_args_list:
            db_name = c[0][0] if c[0] else c[1]["database_name"]
            assert isinstance(
                db_name, str
            ), f"database_name should be str, got {type(db_name)}: {db_name}"

    with patch(
        "luracoin.chain.open_database", wraps=open_database
    ) as mock_open:
        chain.tip
        for c in mock_open.call_args_list:
            db_name = c[0][0] if c[0] else c[1]["database_name"]
            assert isinstance(
                db_name, str
            ), f"database_name should be str, got {type(db_name)}: {db_name}"


def test_get_blk_file_size() -> None:
    chain = Chain()
    Config.MAX_FILE_SIZE = 1000  # Override the max file size for the test

    path = f"{Config.BLOCKS_DIR}testblock"

    f = open(path, "a")
    f.write("".join("x" for _ in range(100)))
    f.close()

    assert get_blk_file_size("testblock") == 100
