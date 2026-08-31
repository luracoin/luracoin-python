# conftest.py
import pytest
import os
import redis

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.chain import close_databases


def init_blockchain():
    """
    Initialize blockchain with genesis block
    """
    coinbase_transacion = Transaction(
        chain=1,
        nonce=8763,
        fee=100,
        value=50000,
        from_address="0" * 34,
        to_address="1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP",
        unlock_sig=None,
    )

    Block(
        version=1,
        height=0,
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff",
        nonce=0,
        txns=[coinbase_transacion],
    )


@pytest.fixture()
def blockchain() -> Generator:
    Config.REDIS_DB = Config.REDIS_DB_TESTS

    folder = Config.BLOCKS_DIR
    os.makedirs(folder, exist_ok=True)

    init_blockchain()

    yield None

    try:
        redis_client = redis.Redis(
            host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
        )
        redis_client.flushdb()
    except redis.exceptions.ConnectionError:
        pass


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmp_path):
    """Give every test a process-safe, disposable blockchain directory."""

    print("Init tests")
    previous = {
        "DATA_TEST_PATH": Config.DATA_TEST_PATH,
        "DATA_TEST_DIR": Config.DATA_TEST_DIR,
        "BLOCKS_TEST_DIR": Config.BLOCKS_TEST_DIR,
        "DATA_DIR": Config.DATA_DIR,
        "BLOCKS_DIR": Config.BLOCKS_DIR,
        "REDIS_DB": Config.REDIS_DB,
    }
    test_data_path = tmp_path / "data"
    blocks_path = test_data_path / "blocks"
    test_data_dir = f"{test_data_path}{os.sep}"
    blocks_dir = f"{blocks_path}{os.sep}"

    close_databases()
    blocks_path.mkdir(parents=True)
    Config.DATA_TEST_PATH = test_data_path
    Config.DATA_TEST_DIR = test_data_dir
    Config.BLOCKS_TEST_DIR = blocks_dir
    Config.REDIS_DB = Config.REDIS_DB_TESTS
    Config.DATA_DIR = test_data_dir
    Config.BLOCKS_DIR = blocks_dir

    try:
        yield
    finally:
        close_databases()
        for name, value in previous.items():
            setattr(Config, name, value)
    """
    redis_client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )

    redis_client.flushdb()
    """
