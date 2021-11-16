import json
import redis
import pytest
from random import randint
from luracoin.config import Config
from luracoin.blocks import Block
from tests.constants import WALLET_1, WALLET_2, WALLET_3
from binascii import unhexlify
from luracoin.transactions import (
    Transaction,
    sign_transaction,
    is_valid_unlocking_script,
)
from operator import itemgetter



def test_updates_the_block_height(blockchain):
    assert False


def test_block_is_saved_in_dat_files_and_reference_is_updated(blockchain):
    assert False