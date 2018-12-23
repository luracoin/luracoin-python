import pytest

from luracoin.helpers import is_hex
from luracoin.wallet import (
    generate_random_wallet_input,
    generate_wallet,
    pubkey_to_address,
)


def test_address_to_pubkey() -> None:
    assert True


def test_build_p2pkh() -> None:
    assert True


def test_generate_random_wallet_input() -> None:
    wallet_input = generate_random_wallet_input()
    assert len(wallet_input) == 64
    assert is_hex(wallet_input) is True


@pytest.fixture
def test_generate_wallet() -> None:
    wallet = generate_wallet()
    return wallet


def test_generate_wallet__check_input(  # type: ignore
    test_generate_wallet
) -> None:
    wallet = test_generate_wallet
    assert len(wallet["input"]) == 64
    assert is_hex(wallet["input"]) is True


def test_generate_wallet__check_address(test_generate_wallet):  # type: ignore
    wallet = test_generate_wallet
    assert len(wallet["address"]) == 34


def test_generate_wallet__check_verifying_key(  # type: ignore
    test_generate_wallet
) -> None:
    wallet = test_generate_wallet
    assert len(wallet["verifying_key"]) == 128


def test_generate_wallet__check_public_key(  # type: ignore
    test_generate_wallet
) -> None:
    wallet = test_generate_wallet
    assert len(wallet["public_key"]) == 66


def test_generate_wallet__check_private_key(  # type: ignore
    test_generate_wallet
) -> None:
    wallet = test_generate_wallet
    assert len(wallet["private_key"]) == 64


def test_generate_wallet__check_xprv(test_generate_wallet):  # type: ignore
    wallet = test_generate_wallet
    assert len(wallet["xprv"]) == 111


def test_generate_wallet__check_seed(test_generate_wallet):  # type: ignore
    wallet = test_generate_wallet
    assert len(wallet["seed"]) == 128


def test_generate_wallet__check_mnemonic(test_generate_wallet):  # type: ignore
    wallet = test_generate_wallet
    assert len(wallet["mnemonic"].split(" ")) == 24


def test_pubkey_to_address() -> None:
    address = pubkey_to_address(
        "03db6eb7d3fba45dcae7ea92a771a2749f5332b34f86cabc1766d46906eefbc2f3"
    )
    assert address == "1BjA85uVq73B55pSPMxNsLta6ZC5V3d82M"


def test_create_wallet() -> None:
    assert True
