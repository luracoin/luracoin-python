import hashlib
import json
import os
import random
from binascii import unhexlify

import ecdsa
from base58 import b58decode_check, b58encode_check
from bip32utils import BIP32Key
from mnemonic import Mnemonic

from luracoin.config import Config
from luracoin.exceptions import WalletAlreadyExistError
from luracoin.helpers import little_endian


def address_to_pubkey(address: str) -> str:
    return b58decode_check(address).hex()


def build_p2pkh(address: str) -> str:
    """
    We have to provide a signature and the original Public Key.
    <OP_DUP>: (0x76) pushes a copy of the topmost stack item on to the stack.
    <OP_HASH160>: (0xa9) consumes the topmost item on the stack, computes the
        RIPEMD160(SHA256()) hash of that item, and pushes that hash onto the
        stack.
    <OP_EQUAL>: (0x87) consumes the top two items on the stack, compares them,
        and pushes true onto the stack if they are the same, false if not.
    <OP_VERIFY>: (0x69) consumes the topmost item on the stack. If that item
        is zero (false) it terminates the script in failure.
    <OP_EQUALVERIFY>: (0x88) runs OP_EQUAL and then OP_VERIFY in sequence.
    <OP_CHECKSIG>: (0xac) consumes a signature and a full public key, and
        pushes true onto the stack if the transaction data specified by the
        SIGHASH flag was converted into the signature using the same ECDSA
        private key that generated the public key. Otherwise, it pushes false
        onto the stack.

    If the byte is < 0x4b (75) it means that is data to push into the STACK
    """
    pub_key_hash = address_to_pubkey(address)
    count_push = little_endian(num_bytes=1, data=int(len(pub_key_hash) / 2))

    # "<OP_DUP><OP_HASH160>len_push pub_key<OP_EQUALVERIFY><OP_CHECKSIG>"
    script = "76a9" + count_push + pub_key_hash + "88ac"
    return script


def generate_random_wallet_input() -> str:
    hexdigits = "0123456789ABCDEF"
    myhex = "".join([hexdigits[random.randint(0, 0xF)] for _ in range(64)])
    return myhex


def create_wallet() -> dict:
    path = Config.WALLET_PATH

    if os.path.exists(path):
        raise WalletAlreadyExistError(f"Wallet already exist in {path}")

    bin_dir = Config.BASE_DIR + "/bin/"
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)

    wallet = generate_wallet()
    with open(path, "wb") as f:
        f.write(json.dumps(wallet).encode())

    return wallet


def generate_wallet() -> dict:
    mnemo = Mnemonic("english")
    data = generate_random_wallet_input()
    code = mnemo.to_mnemonic(unhexlify(data))
    seed = Mnemonic.to_seed(code, passphrase="LURA")
    xprv = BIP32Key.fromEntropy(seed).ExtendedKey()
    priv = BIP32Key.fromEntropy(seed).PrivateKey()
    wif = BIP32Key.fromEntropy(seed).PublicKey()

    signing_key = ecdsa.SigningKey.from_string(priv, curve=ecdsa.SECP256k1)
    verifying_key = signing_key.get_verifying_key()

    wallet = {
        "input": data,
        "mnemonic": code,
        "seed": seed.hex(),
        "xprv": xprv,
        "private_key": priv.hex(),
        "public_key": wif.hex(),
        "verifying_key": verifying_key.to_string().hex(),
        "address": pubkey_to_address(wif),
    }
    return wallet


def pubkey_to_address(pubkey: bytes) -> str:
    if "ripemd160" not in hashlib.algorithms_available:
        raise RuntimeError("missing ripemd160 hash algorithm")

    sha = hashlib.sha256(pubkey).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    return b58encode_check(b"\x00" + ripe)
