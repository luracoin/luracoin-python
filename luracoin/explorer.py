import pytest
import os
import shutil
import redis

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.pow import proof_of_work
from luracoin.client import generate_wallet

"""
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


print(block1.json())

nonce = proof_of_work(block1)
print("=====> POW: " + str(nonce))
block1.nonce = nonce
block1.save()
"""

a = 0
b = 0

for _ in range(1000):
    wallet = generate_wallet()
    if wallet["address"].startswith("L"):
        a += 1
    else:
        b += 1

print(a, b)