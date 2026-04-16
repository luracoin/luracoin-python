import pytest
import os
from binascii import unhexlify
from luracoin.wallet import (
    address_to_pubkey, build_p2pkh, create_wallet,
    pubkey_to_address, generate_wallet,
)
from luracoin.config import Config
from luracoin.exceptions import WalletAlreadyExistError


def test_address_to_pubkey():
    """address_to_pubkey should decode a Base58Check address to hex."""
    address = "LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx"
    result = address_to_pubkey(address)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_p2pkh_returns_decoded_pubkey():
    address = "LVx7PJDKumHEKtWbZVwg9MxLJmZMf7bdGx"
    result = build_p2pkh(address)
    assert result == address_to_pubkey(address)


def test_pubkey_to_address_returns_string():
    pubkey = unhexlify("03db6eb7d3fba45dcae7ea92a771a2749f5332b34f86cabc1766d46906eefbc2f3")
    address = pubkey_to_address(pubkey)
    assert isinstance(address, str)


def test_pubkey_to_address_starts_with_L():
    pubkey = unhexlify("03db6eb7d3fba45dcae7ea92a771a2749f5332b34f86cabc1766d46906eefbc2f3")
    address = pubkey_to_address(pubkey)
    assert address.startswith("L")


def test_pubkey_to_address_length_34():
    pubkey = unhexlify("03db6eb7d3fba45dcae7ea92a771a2749f5332b34f86cabc1766d46906eefbc2f3")
    address = pubkey_to_address(pubkey)
    assert len(address) == 34


def test_pubkey_to_address_deterministic():
    pubkey = unhexlify("03db6eb7d3fba45dcae7ea92a771a2749f5332b34f86cabc1766d46906eefbc2f3")
    assert pubkey_to_address(pubkey) == pubkey_to_address(pubkey)


def test_create_wallet_saves_file(tmp_path):
    wallet_path = str(tmp_path / "wallet.dat")
    Config.WALLET_PATH = wallet_path
    Config.BASE_DIR = str(tmp_path)

    wallet = create_wallet()
    assert os.path.exists(wallet_path)
    assert "address" in wallet
    assert "private_key" in wallet


def test_create_wallet_raises_if_exists(tmp_path):
    wallet_path = str(tmp_path / "wallet.dat")
    Config.WALLET_PATH = wallet_path
    Config.BASE_DIR = str(tmp_path)

    create_wallet()
    with pytest.raises(WalletAlreadyExistError):
        create_wallet()


def test_generate_wallet_all_fields():
    wallet = generate_wallet()
    expected_keys = ["input", "mnemonic", "seed", "xprv", "private_key", "public_key", "verifying_key", "address"]
    for key in expected_keys:
        assert key in wallet, f"Missing key: {key}"
