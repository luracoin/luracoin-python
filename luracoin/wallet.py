import hashlib
import hmac
import json
import os
import secrets
import tempfile
from binascii import unhexlify

from base58 import b58decode_check, b58encode_check
from coincurve import PrivateKey
from mnemonic import Mnemonic

from luracoin.config import Config
from luracoin.exceptions import WalletAlreadyExistError


def address_to_pubkey(address: str) -> str:
    return b58decode_check(address).hex()


def is_valid_address(address: str) -> bool:
    """Return whether ``address`` is a 0x30 Luracoin Base58Check address."""
    if not isinstance(address, str) or len(address) != 34:
        return False
    try:
        payload = b58decode_check(address)
    except (TypeError, ValueError):
        return False
    return len(payload) == 21 and payload[0] == 0x30


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

    return pub_key_hash


def generate_random_wallet_input() -> str:
    """Return 256 bits from the operating system CSPRNG as uppercase hex."""
    return secrets.token_bytes(32).hex().upper()


def create_wallet() -> dict:
    path = Config.WALLET_PATH

    if os.path.lexists(path):
        raise WalletAlreadyExistError(f"Wallet already exist in {path}")

    Config.ensure_data_dirs()
    wallet = generate_wallet()
    payload = json.dumps(wallet).encode()
    parent = os.path.dirname(path)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".wallet-", dir=parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

        # Hard-link publication is atomic and, unlike os.replace(), refuses to
        # overwrite an existing file or symlink created by another process.
        os.link(temporary_path, path, follow_symlinks=False)
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError as exc:
        raise WalletAlreadyExistError(
            f"Wallet already exist in {path}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass

    return wallet


def generate_wallet() -> dict:
    mnemo = Mnemonic("english")
    data = generate_random_wallet_input()
    code = mnemo.to_mnemonic(unhexlify(data))
    seed = Mnemonic.to_seed(code, passphrase="LURA")
    priv, chain_code, signing_key = _bip32_master_key(seed)
    public_key = signing_key.public_key
    compressed_public_key = public_key.format(compressed=True)
    raw_public_key = public_key.format(compressed=False)[1:]

    wallet = {
        "input": data,
        "mnemonic": code,
        "seed": seed.hex(),
        "xprv": _serialize_root_xprv(priv, chain_code),
        "private_key": priv.hex(),
        "public_key": compressed_public_key.hex(),
        "verifying_key": raw_public_key.hex(),
        "address": pubkey_to_address(compressed_public_key),
    }
    return wallet


def _bip32_master_key(seed: bytes) -> tuple[bytes, bytes, PrivateKey]:
    """Derive the BIP32 root private key and chain code from ``seed``."""
    if not isinstance(seed, bytes) or len(seed) < 16:
        raise ValueError("BIP32 seed must contain at least 128 bits.")

    material = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    private_key, chain_code = material[:32], material[32:]
    try:
        signing_key = PrivateKey(private_key)
    except ValueError as exc:
        # BIP32 defines zero and scalars outside the secp256k1 group as
        # invalid master keys. Callers can generate a fresh mnemonic.
        raise ValueError(
            "BIP32 produced an invalid master private key."
        ) from exc
    return private_key, chain_code, signing_key


def _serialize_root_xprv(private_key: bytes, chain_code: bytes) -> str:
    """Serialize a mainnet-version BIP32 root extended private key."""
    payload = (
        b"\x04\x88\xad\xe4"  # xprv version
        + b"\x00"  # depth
        + b"\x00" * 4  # parent fingerprint
        + b"\x00" * 4  # child number
        + chain_code
        + b"\x00"
        + private_key
    )
    encoded = b58encode_check(payload)
    return encoded.decode() if isinstance(encoded, bytes) else encoded


def pubkey_to_address(pubkey: bytes) -> str:
    if "ripemd160" not in hashlib.algorithms_available:
        raise RuntimeError("missing ripemd160 hash algorithm")

    sha = hashlib.sha256(pubkey).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    address = b58encode_check(b"\x30" + ripe)
    if isinstance(address, bytes):
        address = address.decode()
    if len(address) != 34:
        raise RuntimeError("Invalid address")
    return address
