import pytest
import os
import shutil
import redis

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.pow import proof_of_work


coinbase_transacion = Transaction(
    chain=1,
    nonce=8763,
    fee=100,
    value=50000,
    to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
    unlock_sig=None,
)

block1 = Block(
    version=1,
    height=0,
    prev_block_hash="0" * 64,
    timestamp=1_623_168_442,
    bits=b"\x1e\x0f\xff\xff",
    nonce=0,
    txns=[coinbase_transacion],
)

print(block1.json())

nonce = proof_of_work(block1)
print("=====> POW: " + str(nonce))
block1.nonce = nonce
block1.save()
