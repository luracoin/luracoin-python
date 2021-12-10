"""import time
import pytest
import os
import shutil
import redis
import json
from random import randint
import rocksdb

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.pow import proof_of_work
from luracoin.client import generate_wallet
from luracoin.chain import set_value, get_value
from luracoin.helpers import sha256d
"""
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


"""
# GENERATE 1K addresses

a = 0
b = 0

for _ in range(1000):
    wallet = generate_wallet()
    if wallet["address"].startswith("L"):
        a += 1
    else:
        b += 1
print(a, b)
"""
"""
db = rocksdb.DB("test.db", rocksdb.Options(create_if_missing=True))


a = 0
b = 0
for i in range(3000000):
    print(f"{i}/3000000 || a: {a} / b: {b}")
    wallet = generate_wallet()
    db.put(wallet["address"].encode(), randint(20000, 500000000).to_bytes(8, byteorder="little", signed=False))

    if wallet["address"].startswith("L"):
        a += 1
    else:
        b += 1
"""
"""
count = 0
it = db.iteritems()
it.seek_to_first()

accounts = {}
start = time.time()

for _ in range(40):
    for k, v in it:
        count += 1
        if len(v) > 8:
            db.delete(k)
        else:
            accounts[k.decode()] = int.from_bytes(v, byteorder="little", signed=False)

for _ in range(40):
    accounts_ordered = {}
    for k in sorted(accounts):
        accounts_ordered[k] = accounts[k]



accounts_ordered = {}
for k in sorted(accounts):
    accounts_ordered[k] = accounts[k]

print(json.dumps(accounts_ordered))
print(sha256d(json.dumps(accounts_ordered).encode()))

print("\n\n\n\n")
print(f"Total time: {time.time() - start}")
print(f"Total: {count}")
"""

"""
set_value(
    Config.DATABASE_ACCOUNTS, 
    "marcos".encode(), 
    int(100).to_bytes(8, byteorder="little", signed=False)
)


print(get_value(Config.DATABASE_ACCOUNTS, "marcos".encode()))
"""

import binascii
import json
from binascii import unhexlify
from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from tests.helpers import add_test_transactions
from luracoin.config import Config
from luracoin.pow import proof_of_work
from luracoin.chain import Chain
from tests.constants import WALLET_1

START_TIMESTAMP = 1639159886
chain = Chain()

block1 = Block(
    version=1,
    height=0,
    prev_block_hash="0" * 64,
    miner=WALLET_1["address"],
    timestamp=START_TIMESTAMP,
    bits=Config.STARTING_DIFFICULTY,
    nonce=156369,
    txns=[],
)
nonce = proof_of_work(block1)
print("=====> POW: " + str(nonce))

print(json.dumps(block1.json(), indent=4))

# Transaction to stack 15 Luracoins
transaction_1 = Transaction(
    chain=1,
    nonce=1,
    fee=0,
    value=Config.LURASHIS_PER_COIN * 15,
    to_address=Config.STAKING_ADDRESS,
)

transaction_1.sign(unhexlify(WALLET_1["private_key"]))
assert transaction_1.validate() == True

block2 = Block(
    version=1,
    height=1,
    prev_block_hash=block1.id,
    miner=WALLET_1["address"],
    timestamp=START_TIMESTAMP + (3*60),  # 3 minutes
    bits=Config.STARTING_DIFFICULTY,
    nonce=4358788,
    txns=[transaction_1],
)

nonce = proof_of_work(block2)
print("=====> POW: " + str(nonce))

print(json.dumps(block2.json(), indent=4))

assert chain.height == 0
chain.add_block(block1)
assert chain.height == 0
chain.add_block(block2)
assert chain.height == 1

assert False
