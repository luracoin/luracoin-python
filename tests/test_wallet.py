import pytest

from luracoin.helpers import is_hex
from luracoin.wallet import (
    address_to_pubkey,
    build_p2pkh,
    create_wallet,
    generate_random_wallet_input,
    generate_wallet,
    pubkey_to_address,
)


def test_address_to_pubkey():
    assert True


def test_build_p2pkh():
    assert True


def test_generate_random_wallet_input():
    wallet_input = generate_random_wallet_input()
    assert len(wallet_input) == 64
    assert is_hex(wallet_input) is True


@pytest.fixture
def test_generate_wallet():
    assert True


def test_generate_wallet__check_address(test_generate_wallet):
    assert True


def test_generate_wallet__check_verifying_key(test_generate_wallet):
    assert True


def test_generate_wallet__check_public_key(test_generate_wallet):
    assert True


def test_generate_wallet__check_private_key(test_generate_wallet):
    assert True


def test_generate_wallet__check_xprv(test_generate_wallet):
    assert True


def test_generate_wallet__check_seed(test_generate_wallet):
    assert True


def test_generate_wallet__check_mnemonic(test_generate_wallet):
    assert True


def test_pubkey_to_address():
    assert True


def test_create_wallet():
    assert True
