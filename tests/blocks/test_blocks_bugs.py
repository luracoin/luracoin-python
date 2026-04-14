from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from tests.constants import WALLET_1


def test_block_default_txns_not_shared_between_instances():
    """
    Bug 1.5: Block.__init__ uses txns=[] as default argument.
    Mutable default arguments are shared between all instances,
    so modifying one block's txns would affect another.
    """
    block_a = Block(version=1, height=0, miner="L" * 34, prev_block_hash="0" * 64,
                    timestamp=1000, bits=b"\x1f\x00\xff\xff", nonce=0)
    block_b = Block(version=1, height=1, miner="L" * 34, prev_block_hash="0" * 64,
                    timestamp=2000, bits=b"\x1f\x00\xff\xff", nonce=0)

    assert block_a.txns is not block_b.txns
    assert block_a.txns == []
    assert block_b.txns == []


def test_block_save_no_debug_prints(capsys):
    """
    Bug 1.4: Block.save() contains debug print() calls that should not
    be in production code.
    """
    coinbase_tx = Transaction(
        chain=1, nonce=1, fee=0, value=50000,
        from_address="0" * 34,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1d\x0f\xff\xff", nonce=12308683,
        txns=[coinbase_tx],
    )

    block.save()
    captured = capsys.readouterr()
    assert captured.out == ""
