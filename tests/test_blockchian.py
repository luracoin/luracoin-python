import pytest
import json
import redis
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
from tests.helpers import add_test_transactions


@pytest.mark.skip(reason="WIP")
def test_block_select_transactions():
    redis_client = redis.Redis(
        host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
    )
    redis_client.flushdb()

    transactions = add_test_transactions()

    assert len(redis_client.keys()) == 5

    block1 = Block(
        version=1,
        prev_block_hash=0,
        timestamp=1_623_168_442,
        signature="0",
        txns=[],
    )

    block1.select_transactions()

    txns_list = [
        {
            "id": transactions[0].id,
            "signature": transactions[0].unlock_sig.hex(),
        },
        {
            "id": transactions[1].id,
            "signature": transactions[1].unlock_sig.hex(),
        },
        {
            "id": transactions[2].id,
            "signature": transactions[2].unlock_sig.hex(),
        },
        {
            "id": transactions[3].id,
            "signature": transactions[3].unlock_sig.hex(),
        },
        {
            "id": transactions[4].id,
            "signature": transactions[4].unlock_sig.hex(),
        },
    ]

    newlist = sorted(txns_list, key=itemgetter("id"))

    assert block1.txns[0].id == newlist[0]["id"]
    assert block1.txns[1].id == newlist[1]["id"]
    assert block1.txns[2].id == newlist[2]["id"]
    assert block1.txns[3].id == newlist[3]["id"]
    assert block1.txns[4].id == newlist[4]["id"]


@pytest.mark.skip(reason="WIP")
def test_block_validate(blockchain):
    assert False
