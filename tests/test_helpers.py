from luracoin.config import Config
from luracoin.helpers import (
    bits_to_target,
    little_endian,
    var_int,
    is_hex,
    get_blk_file_size,
    block_index_disk_read,
    block_index_disk_write,
)


def test_block_index_disk_read() -> None:
    block_index = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaafd95010f00000000"
    )
    actual = block_index_disk_read(block_index)
    expected = {
        "header": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "height": 405,
        "txns": 15,
        "file": "000000",
        "is_validated": False,
    }
    assert actual == expected

    block_index = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaa050f00000000"
    )
    actual = block_index_disk_read(block_index)
    expected = {
        "header": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "height": 5,
        "txns": 15,
        "file": "000000",
        "is_validated": False,
    }
    assert actual == expected

    block_index = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaafe73c60800fd45462b4e0201"
    )
    actual = block_index_disk_read(block_index)
    expected = {
        "header": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "height": 575_091,
        "txns": 17989,
        "file": "151083",
        "is_validated": True,
    }
    assert actual == expected


def test_block_index_disk_write() -> None:
    block_index = {
        "header": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "height": 5,
        "txns": 15,
        "file": "000000",
        "is_validated": False,
    }

    actual = block_index_disk_write(block_index)
    expected = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaa050f00000000"
    )

    assert actual == expected

    block_index = {
        "header": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "height": 575_091,
        "txns": 17989,
        "file": "151083",
        "is_validated": True,
    }
    actual = block_index_disk_write(block_index)
    expected = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaafe73c60800fd45462b4e0201"
    )

    assert actual == expected


def test_var_int() -> None:
    assert var_int(252) == "fc"
    assert var_int(1276) == "fdfc04"
    assert var_int(10276) == "fd2428"
    assert var_int(100_000) == "fea0860100"
    assert var_int(1_000_000) == "fe40420f00"
    assert var_int(10_000_000) == "fe80969800"
    assert var_int(5_000_000_000) == "ff00f2052a01000000"


def test_little_endian() -> None:
    assert little_endian(num_bytes=5, data=15) == "0f00000000"
    assert little_endian(num_bytes=4, data=15) == "0f000000"
    assert little_endian(num_bytes=3, data=15) == "0f0000"
    assert little_endian(num_bytes=2, data=19) == "1300"
    assert little_endian(num_bytes=1, data=19) == "13"


def test_is_hex() -> None:
    assert (
        is_hex(
            "C4490C4A562C73F32F97A216B41482AE4174471BA89BAF69846D8BF266F3A6E2"
        )
        is True
    )

    assert (
        is_hex(
            "eec0eaf1e71b1b20fa72e5f1b7e7c94b4c90351d3eca003a49493431fadf4a01"
        )
        is True
    )

    assert (
        is_hex(
            "a22b96d13846af2198de9fecd9d4076d1a8a5bd6686055041c90c8c5b9b644a9"
        )
        is True
    )

    assert (
        is_hex(
            "478db2b902797bd1d464a0553a7ba53c60a191439243451b7376688d1ae5a5f8"
        )
        is True
    )

    assert (
        is_hex(
            "5b55cae2711fa7495c38ecbe3ae459fe6a2542b424a983cc6ed9a785b2bd03fe"
        )
        is True
    )

    assert is_hex("5b55cae2711fa7495c38ecbe3ae459fe6a2542b424a983cc6") is False

    assert (
        is_hex(
            "YOU8UZH507MOKZIB5c38ecbe3ae459fe6a2542b424a983cc6ed9a785b2bd03fe"
        )
        is False
    )

    assert (
        is_hex(
            "yw7zozr07x654wwg9e7b09dc6827f1ad48084801b8a602883c3d77ff07fa66ba"
        )
        is False
    )


def test_sha256d() -> None:
    # TODO: Test for sha256d
    pass


def test_var_int_to_bytes() -> None:
    # TODO: Test for var_int_to_bytes
    pass


def test_bits_to_target() -> None:
    assert bits_to_target("1d00ffff") == (
        "00000000ffff0000000000000000000000000000000000000000000000000000"
    )

    assert bits_to_target("1731D97C") == (
        "00000000000000000031D97C0000000000000000000000000000000000000000"
    )

    assert bits_to_target("17272fbd") == (
        "000000000000000000272fbd0000000000000000000000000000000000000000"
    )

    assert bits_to_target("1b4766ed") == (
        "00000000004766ed000000000000000000000000000000000000000000000000"
    )

    assert bits_to_target("1dffffff") == (
        "000000ffffff0000000000000000000000000000000000000000000000000000"
    )


def test_get_blk_file_size(blockchain) -> None:  # type: ignore
    testfilename = "testfile.txt"
    testfile = f"{Config.BLOCKS_DIR}{testfilename}"
    content_length = 1000

    f = open(testfile, "a")
    f.write("".join("x" for _ in range(content_length)))
    f.close()

    assert get_blk_file_size(testfilename) == content_length
