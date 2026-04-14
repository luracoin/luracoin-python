from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.pow import proof_of_work
from tests.constants import WALLET_1


def test_proof_of_work():
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    assert not block.is_valid_proof() or block.nonce == 0

    nonce = proof_of_work(block)
    assert block.nonce == nonce
    assert block.is_valid_proof()
