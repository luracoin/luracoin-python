import binascii
import pytest
import json
from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from tests.helpers import add_test_transactions
from luracoin.config import Config
from luracoin.pow import proof_of_work


@pytest.mark.skip(reason="WIP")
def test_validate():
    coinbase_transaction_1 = Transaction(
        chain=1,
        nonce=1,
        fee=0,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block1 = Block(
        version=1,
        height=0,
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=b"\x1e\x0f\xff\xff",
        nonce=0,
        txns=[coinbase_transaction_1],
    )

    assert block1.validate() is False

    proof_of_work(block=block1, starting_at=4334955)
    assert block1.nonce == 4334956
    assert block1.validate() is True

    transactions = add_test_transactions()

    coinbase_transaction_2 = Transaction(
        chain=1,
        nonce=2,
        fee=0,
        value=50000,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block2 = Block(
        version=1,
        height=1,
        prev_block_hash=block1.id,
        timestamp=1_623_208_442,
        bits=b"\x1e\x0f\xff\xff",
        nonce=0,
        txns=[coinbase_transaction_2, *transactions],
    )

    proof_of_work(block=block2, starting_at=1162892)
    assert block2.nonce == 1162893
