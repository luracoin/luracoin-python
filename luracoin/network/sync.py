"""
Sequential block synchronization.
"""

import binascii

from luracoin.config import Config
from luracoin.network.protocol import (
    INV_BLOCK,
    build_getblocks_payload,
    build_inv_payload,
)

# Public compatibility alias; requests themselves read the runtime config.
SYNC_BATCH_SIZE = Config.SYNC_BATCH_SIZE


class BlockSync:
    """Handles downloading and applying blocks from a peer."""

    def __init__(self, chain, block_cls):
        """
        chain: Chain instance (for tip, get_account, etc.)
        block_cls: Block class (for deserializing and saving)
        """
        self.chain = chain
        self.block_cls = block_cls
        self.syncing = False

    def needs_sync(self, remote_height: int) -> bool:
        """Do we need blocks from this peer?"""
        return remote_height > self.chain.tip

    def build_getblocks_request(self) -> bytes:
        """Build a GETBLOCKS payload starting from our tip + 1."""
        start = self.chain.tip + 1
        return build_getblocks_payload(start, Config.SYNC_BATCH_SIZE)

    def handle_block(self, block_data: bytes) -> bool:
        """
        Deserialize, validate, and save a received block.
        Returns True if accepted, False if rejected.
        """
        try:
            block = self.block_cls()
            block.deserialize(block_data)
        except Exception:
            return False

        expected_height = self.chain.tip + 1
        if block.height != expected_height:
            return False

        try:
            if not block.validate():
                return False
            block.save()
        except Exception:
            return False
        return True

    def build_block_inv(self, block_id_hex: str) -> bytes:
        """Build an INV message for a newly mined block."""
        hash_bytes = binascii.unhexlify(block_id_hex)
        return build_inv_payload(INV_BLOCK, hash_bytes)

    def should_request_block(self, inv_hash: bytes) -> bool:
        """
        Check if we need a block advertised via INV.
        We check if we already have it by trying to find it.
        """
        # Simple check: we don't have an index of block hashes,
        # so we just check if we might need it based on height gap.
        # In practice, a full node would maintain a hash index.
        # For now, always request -- the validate step will reject duplicates.
        return True
