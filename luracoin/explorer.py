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

LURASHIS_PER_COIN = int(100e6)
BASE_REWARD = 50 * LURASHIS_PER_COIN
HALVING_BLOCKS = 172_800 * 1.5

def mining_reward(height) -> int:
    halving = int(height / HALVING_BLOCKS) + 1
    return int(BASE_REWARD / halving)


cont = 0
total = 0
reward = mining_reward(cont)
while reward > 0:
    cont += 1
    reward = mining_reward(cont)
    total += reward

    print(f"Height: {cont}\tYear: {int(cont/172800)}\tSupply: {total / LURASHIS_PER_COIN}\tReward: {int(reward) / LURASHIS_PER_COIN}")

    if reward <= 1_000 :
        break

print("====================")
print(f"Total supply: {total}")
print(f"Total supply: {total / LURASHIS_PER_COIN}")
print(f"Total blocks: {cont}")