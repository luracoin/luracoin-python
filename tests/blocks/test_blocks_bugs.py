from luracoin.blocks import Block
from luracoin.genesis import initialize_chain
from tests.constants import WALLET_1


def test_block_default_txns_not_shared_between_instances():
    """
    Bug 1.5: Block.__init__ uses txns=[] as default argument.
    Mutable default arguments are shared between all instances,
    so modifying one block's txns would affect another.
    """
    block_a = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1000,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
    )
    block_b = Block(
        version=1,
        height=1,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=2000,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
    )

    assert block_a.txns is not block_b.txns
    assert block_a.txns == []
    assert block_b.txns == []


def test_block_save_no_debug_prints(capsys):
    """
    Bug 1.4: Block.save() contains debug print() calls that should not
    be in production code.
    """
    block = initialize_chain()
    capsys.readouterr()
    block.save()
    captured = capsys.readouterr()
    assert captured.out == ""
