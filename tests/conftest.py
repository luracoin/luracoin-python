import pytest
import os
import shutil

from typing import Generator
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction



@pytest.fixture()
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

