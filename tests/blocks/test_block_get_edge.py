import pytest

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.exceptions import BlockNotValidError
from luracoin.genesis import initialize_chain


def test_block_get_fails_closed_when_file_has_no_matching_height():
    """A present index pointing at the wrong file is corrupt storage."""
    chain = Chain()

    # Persist the only valid height-zero block for the active network.
    initialize_chain()

    # Manually set block file number for height 999 to file 0
    # File 0 only contains block at height 0, not 999
    chain.set_block_file_number(999, 0)

    with pytest.raises(BlockNotValidError, match="without that height"):
        Block.get(999)
