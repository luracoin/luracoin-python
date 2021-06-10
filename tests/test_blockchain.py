from pymongo import MongoClient
from random import randint
from luracoin.blocks import Block

def test_blockchain():
    block1 = Block(
        version=1,
        prev_block_hash=0,
        timestamp=1623168442,
        bits="bit here",
        nonce=29863,
        txns=[]
    )

    block1.save()

    assert False