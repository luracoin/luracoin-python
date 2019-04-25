import pytest
import os
import shutil

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction
from tests.constants import (
    COINBASE1,
    COINBASE2,
    COINBASE3,
    TRANSACTION1,
    TRANSACTION2,
    TRANSACTION3,
    TRANSACTION4,
    TRANSACTION5,
)


@pytest.fixture(scope="session")
def blockchain() -> Generator:
    Config.DATA_DIR = Config.BASE_DIR + "/tests/data/"
    Config.BLOCKS_DIR = Config.DATA_DIR + "blocks/"

    folder = Config.BLOCKS_DIR
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    yield None

    if os.path.exists(folder):
        shutil.rmtree(folder)


@pytest.fixture
def block1(blockchain) -> Block:  # type: ignore
    block = Block(
        version=1,
        prev_block_hash=Config.COINBASE_TX_ID,
        timestamp=1_501_821_412,
        bits="1e0fffff",
        nonce=337_176,
    )
    block.txns = [COINBASE1]
    return block


@pytest.fixture
def block2(blockchain, block1) -> Block:  # type: ignore
    block = Block(
        version=1,
        prev_block_hash=block1.id,
        timestamp=1_501_821_412,
        bits="1e0fffff",
        nonce=528_602,
    )
    block.txns = [
        COINBASE2,
        TRANSACTION1,
        TRANSACTION2,
        TRANSACTION3,
        TRANSACTION4,
        TRANSACTION5,
    ]
    return block


@pytest.fixture
def block3(blockchain, block2) -> Block:  # type: ignore
    block = Block(
        version=1,
        prev_block_hash=block2.id,
        timestamp=1_501_821_412,
        bits="1e0fffff",
        nonce=1_940_600,
    )
    block.txns = [COINBASE3]
    return block


@pytest.fixture
def coinbase_tx1() -> Transaction:
    return COINBASE1


@pytest.fixture
def coinbase_tx2() -> Transaction:
    return COINBASE2


@pytest.fixture
def transaction1() -> Transaction:
    return TRANSACTION1


@pytest.fixture
def transaction2() -> Transaction:
    return TRANSACTION2


@pytest.fixture
def transaction3() -> Transaction:
    return TRANSACTION3


@pytest.fixture
def transaction4() -> Transaction:
    return TRANSACTION4


@pytest.fixture
def transaction5() -> Transaction:
    return TRANSACTION5
