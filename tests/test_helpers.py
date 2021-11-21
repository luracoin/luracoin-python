import pytest
from luracoin.config import Config
from luracoin.helpers import bits_to_target, is_hex, bytes_to_signing_key


def test_bytes_to_signing_key(blockchain):
    private_key_original = (
        b"JRh3y\xf3\xcfg\x8d\xea.\x91\xeb?\xed\xe3u\x04\x84[R\x9c\x97\x87\x8f"
        b"\xc6I\x8b(w\xd5\xb1"
    )

    private_key = bytes_to_signing_key(private_key=private_key_original)
    verifying_key = private_key.get_verifying_key()

    assert private_key.to_string() == private_key_original
    assert private_key.to_string().hex() == (
        "4a52683379f3cf678dea2e91eb3fede37504845b529c97878fc6498b2877d5b1"
    )
    assert verifying_key.to_string().hex() == (
        "5c440bc46d316dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1eab11"
        "c4af165e4ce3eb0652f8d937620804fe15201c00a7466f56237810988db1"
    )


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


@pytest.mark.skip(reason="WIP")
def test_sha256d() -> None:
    # TODO: Test for sha256d
    pass


def test_bits_to_target() -> None:
    assert bits_to_target(b"\x1d\x00\xff\xff") == (
        "00000000ffff0000000000000000000000000000000000000000000000000000"
    )

    assert bits_to_target(b"\x12\x00\xff\xff") == (
        "000000000000000000000000000000ffff000000000000000000000000000000"
    )

    assert bits_to_target(b"\x04\x00\xff\xff") == (
        "0000000000000000000000000000000000000000000000000000000000ffff00"
    )

    assert bits_to_target(b"\x1f\x00\xff\xff") == (
        "0000ffff00000000000000000000000000000000000000000000000000000000"
    )
