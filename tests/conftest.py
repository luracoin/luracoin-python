# conftest.py
import pytest
import os
import shutil
import redis

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.pow import proof_of_work


def init_blockchain():
    """
    Initialize blockchain with genesis block
    """
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
        bits=b"\1f\x00\xff\xff",
        nonce=0,
        txns=[coinbase_transacion],
    )

    block1.save()


@pytest.fixture()
def blockchain() -> Generator:
    Config.DATA_DIR = Config.BASE_DIR + "/tests/data/"
    Config.BLOCKS_DIR = Config.DATA_DIR + "blocks/"
    Config.REDIS_DB = Config.REDIS_DB_TESTS

    folder = Config.BLOCKS_DIR
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    init_blockchain()

    yield None

    if os.path.exists(folder):
        shutil.rmtree(folder)

    print("clean tests")
    redis_client = redis.Redis(
        host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
    )

    redis_client.flushdb()


"""
@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir):
    print("Init tests")
    Config.REDIS_DB = Config.REDIS_DB_TESTS
    # Setup: fill with any logic you want

    yield # this is where the testing happens

    # Teardown : fill with any logic you want
    print("clean tests")
    redis_client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )

    redis_client.flushdb()
"""
