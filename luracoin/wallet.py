import hashlib
import logging
import os
from typing import Tuple

import ecdsa
from base58 import b58decode_check, b58encode_check

from .config import Config

logging.basicConfig(
    level=getattr(logging, os.environ.get("TC_LOG_LEVEL", "INFO")),
    format="[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def pubkey_to_address(pubkey: bytes) -> str:
    if "ripemd160" not in hashlib.algorithms_available:
        raise RuntimeError("missing ripemd160 hash algorithm")

    sha = hashlib.sha256(pubkey).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    return b58encode_check(b"\x00" + ripe)


def address_to_pubkey(address: str) -> str:
    return b58decode_check(address).hex()


def bytes_to_signing_key(str_key: bytes) -> ecdsa.SigningKey:
    return ecdsa.SigningKey.from_string(str_key, curve=ecdsa.SECP256k1)


def get_wallet() -> Tuple:
    """
    Reads the wallet file on the system and returns the Signing Key, the
    verifying key and the address.
    """
    with open(Config.WALLET_PATH, "rb") as f:
        signing_key = ecdsa.SigningKey.from_string(
            f.read(), curve=ecdsa.SECP256k1
        )

    verifying_key = signing_key.get_verifying_key()
    my_address = pubkey_to_address(verifying_key.to_string())

    return signing_key, verifying_key, my_address


def create_wallet() -> Tuple:
    signing_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    verifying_key = signing_key.get_verifying_key()
    my_address = pubkey_to_address(verifying_key.to_string())

    return signing_key.to_string(), verifying_key, my_address
