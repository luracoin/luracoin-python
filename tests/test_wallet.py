import pytest

from luracoin.helpers import is_hex
from luracoin.wallet import generate_random_wallet_input


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
    assert True


def test_generate_wallet__check_address(test_generate_wallet):  # type: ignore
    assert True


def test_generate_wallet__check_verifying_key(  # type: ignore
    test_generate_wallet
) -> None:
    assert True


def test_generate_wallet__check_public_key(  # type: ignore
    test_generate_wallet
) -> None:
    assert True


def test_generate_wallet__check_private_key(  # type: ignore
    test_generate_wallet
) -> None:
    assert True


def test_generate_wallet__check_xprv(test_generate_wallet):  # type: ignore
    assert True


def test_generate_wallet__check_seed(test_generate_wallet):  # type: ignore
    assert True


def test_generate_wallet__check_mnemonic(test_generate_wallet):  # type: ignore
    assert True


def test_pubkey_to_address() -> None:
    assert True


def test_create_wallet() -> None:
    assert True
