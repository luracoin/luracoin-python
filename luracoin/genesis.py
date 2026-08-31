"""Network-specific genesis manifests.

The historical address below is present in public test fixtures and its key is
therefore not secret.  It is retained only for testnet/devnet compatibility;
mainnet intentionally has no manifest and cannot start until a new, audited
genesis ceremony supplies one.
"""

from __future__ import annotations

import warnings

from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.transactions import Transaction

GENESIS_ADDRESS = "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"
GENESIS_TIMESTAMP = 1_623_168_442

# These nonces and ids were mined over Block._canonical_hash_bytes. They are
# fixed consensus vectors, not values to regenerate at node startup.
GENESIS_MANIFESTS = {
    "testnet": {
        "chain_id": 1,
        "nonce": 14_121_310,
        "id": (
            "0000009e2bcc8e56cee8b5e0fbdac9ed"
            "c04513542af5c5791ea6165179c468bf"
        ),
    },
    "devnet": {
        "chain_id": 2,
        "nonce": 11_943_016,
        "id": (
            "00000033e4111007fd85423c7a527595"
            "e8efefe158a1250db62a32870857ef91"
        ),
    },
}

_warned_networks = set()


def _active_manifest() -> dict:
    manifest = GENESIS_MANIFESTS.get(Config.NETWORK)
    if manifest is None:
        raise BlockNotValidError(
            "Mainnet genesis is intentionally undefined. Provide and audit a "
            "fresh mainnet genesis manifest before starting this network."
        )
    if Config.CHAIN_ID != manifest["chain_id"]:
        raise BlockNotValidError(
            "Configured network and chain id are inconsistent."
        )
    if Config.NETWORK not in _warned_networks:
        warnings.warn(
            "The development genesis address has a publicly known key; "
            "never use this manifest for assets of value.",
            RuntimeWarning,
            stacklevel=2,
        )
        _warned_networks.add(Config.NETWORK)
    return manifest


def build_genesis_block():
    """Build the exact genesis block committed for this development network."""
    from luracoin.blocks import Block

    manifest = _active_manifest()
    coinbase = Transaction(
        chain=manifest["chain_id"],
        nonce=0,
        fee=0,
        value=Config.COINS_TO_FORGE,
        from_address="0" * 34,
        to_address=GENESIS_ADDRESS,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=0,
        miner=GENESIS_ADDRESS,
        prev_block_hash="0" * 64,
        timestamp=GENESIS_TIMESTAMP,
        bits=Config.STARTING_DIFFICULTY,
        nonce=manifest["nonce"],
        txns=[coinbase],
    )
    if block.id != manifest["id"] or not block.is_valid_proof():
        raise BlockNotValidError(
            "Compiled genesis manifest is internally invalid."
        )
    return block


def validate_genesis_manifest(block) -> None:
    """Reject any height-zero block that differs from the active manifest."""
    manifest = _active_manifest()
    if (
        block.version != 1
        or block.height != 0
        or block.miner != GENESIS_ADDRESS
        or block.prev_block_hash != "0" * 64
        or block.timestamp != GENESIS_TIMESTAMP
        or block.bits != Config.STARTING_DIFFICULTY
        or block.nonce != manifest["nonce"]
        or block.id != manifest["id"]
    ):
        raise BlockNotValidError(
            "Block does not match the active genesis manifest."
        )


def initialize_chain():
    """Persist the canonical genesis once, or verify the existing one."""
    from luracoin.blocks import Block

    # Mainnet and inconsistent config fail before disk access.
    _active_manifest()
    existing = Block.get(0)
    if existing is not None:
        existing._validate_or_raise(check_state=False)
        return existing

    genesis = build_genesis_block()
    genesis.save()
    return genesis
