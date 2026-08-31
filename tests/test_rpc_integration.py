"""End-to-end RPC checks against the real Redis mempool used in CI."""

from binascii import unhexlify

import pytest
import redis
from aiohttp.test_utils import TestClient, TestServer

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.network.node import Node
from luracoin.rpc import RpcServer
from luracoin.transactions import Transaction
from tests.constants import WALLET_1, WALLET_2, WALLET_3


TOKEN = "i" * 48


@pytest.fixture
def live_redis():
    client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )
    try:
        client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("Redis is not available")
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()


@pytest.mark.asyncio
async def test_signed_transaction_round_trips_through_rpc_and_real_mempool(
    live_redis,
):
    Chain().set_account(
        WALLET_1["address"],
        {"balance": 1_000, "nonce": 0},
    )
    transaction = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=5,
        value=100,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(unhexlify(WALLET_1["private_key"]))

    server = TestServer(RpcServer(token=TOKEN).create_app())
    client = TestClient(server)
    await client.start_server()
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        response = await client.post(
            "/v1/transactions",
            headers=headers,
            json={"raw": transaction.serialize().hex()},
        )
        assert response.status == 202
        receipt = await response.json()
        assert receipt["accepted"] is True
        assert receipt["broadcast"] is False
        assert receipt["relay_count"] == 0
        assert receipt["transaction"]["id"] == transaction.id

        response = await client.get(
            f"/v1/accounts/{WALLET_1['address']}",
            headers=headers,
        )
        assert response.status == 200
        account = await response.json()
        assert account["balance"] == "1000"
        assert account["spendable_balance"] == "895"
        assert account["next_nonce"] == 2
        assert account["pending_outgoing_count"] == 1

        response = await client.get(
            f"/v1/accounts/{WALLET_1['address']}/transactions",
            headers=headers,
        )
        assert response.status == 200
        history = await response.json()
        assert history["transactions"][0]["id"] == transaction.id
        assert history["transactions"][0]["status"] == "pending"
        assert history["next_cursor"] is None
    finally:
        await client.close()


def test_confirmed_competitor_removes_real_redis_orphan(live_redis):
    Chain().set_account(
        WALLET_1["address"],
        {"balance": 1_000, "nonce": 0},
    )
    local = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=100,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(unhexlify(WALLET_1["private_key"]))
    confirmed = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=90,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    ).sign(unhexlify(WALLET_1["private_key"]))
    assert local.to_transaction_pool() is True

    node = Node(port=0, seed_nodes=[])
    block = Block(txns=[confirmed])
    captured = node._snapshot_competing_transactions(block)
    assert [
        (transaction.id, payload) for transaction, payload in captured
    ] == [(local.id, local.serialize())]

    # Block persistence clears the confirmed slot before Node can inspect it.
    # The captured exact ID/bytes still allow a conditional orphan cleanup.
    block.clean_mempool()
    assert live_redis.get(local.id) == local.serialize()
    assert live_redis.get(local.mempool_nonce_key) is None

    node._forget_confirmed_transactions(block, captured)
    assert live_redis.get(local.id) is None
