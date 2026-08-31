import json
import os
import stat
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from luracoin.rpc import RpcServer, load_or_create_rpc_token


TOKEN = "t" * 48
KNOWN_ADDRESS = "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"


@pytest.fixture
async def rpc_client():
    server = TestServer(RpcServer(token=TOKEN).create_app())
    client = TestClient(server)
    await client.start_server()
    try:
        yield client
    finally:
        await client.close()


def auth_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_rpc_token_is_persistent_and_private(tmp_path):
    path = tmp_path / "rpc.token"
    first = load_or_create_rpc_token(str(path))
    second = load_or_create_rpc_token(str(path))

    assert first == second
    assert len(first) >= 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_rpc_token_rejects_symlinks_and_short_secrets(tmp_path):
    short_path = tmp_path / "short.token"
    short_path.write_text("not-secret\n", encoding="utf-8")
    short_path.chmod(0o600)
    with pytest.raises(RuntimeError, match="too short"):
        load_or_create_rpc_token(str(short_path))

    target = tmp_path / "real.token"
    target.write_text(f"{'s' * 48}\n", encoding="utf-8")
    link = tmp_path / "linked.token"
    link.symlink_to(target)
    with pytest.raises(RuntimeError, match="not a regular file"):
        load_or_create_rpc_token(str(link))


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_rpc_token_rejects_insecure_permissions_and_whitespace(tmp_path):
    public_path = tmp_path / "public.token"
    public_path.write_text(f"{'p' * 48}\n", encoding="utf-8")
    public_path.chmod(0o644)
    with pytest.raises(RuntimeError, match="group or other access"):
        load_or_create_rpc_token(str(public_path))

    whitespace_path = tmp_path / "whitespace.token"
    whitespace_path.write_text(f"{'s' * 24} {'s' * 24}\n", encoding="utf-8")
    whitespace_path.chmod(0o600)
    with pytest.raises(RuntimeError, match="invalid whitespace"):
        load_or_create_rpc_token(str(whitespace_path))


@pytest.mark.asyncio
async def test_health_is_available_without_token(rpc_client):
    response = await rpc_client.get("/health")
    assert response.status == 200
    assert (await response.json())["ok"] is True


@pytest.mark.asyncio
async def test_private_routes_require_bearer_token(rpc_client):
    response = await rpc_client.get("/v1/status")
    assert response.status == 401

    response = await rpc_client.get("/v1/status", headers=auth_headers())
    assert response.status == 200
    payload = await response.json()
    assert payload["network"] in {"mainnet", "testnet", "devnet"}


@pytest.mark.asyncio
async def test_account_endpoint_validates_address(rpc_client):
    response = await rpc_client.get(
        "/v1/accounts/not-an-address", headers=auth_headers()
    )
    assert response.status == 400

    response = await rpc_client.get(
        f"/v1/accounts/{KNOWN_ADDRESS}", headers=auth_headers()
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["network"] in {"mainnet", "testnet", "devnet"}
    assert payload["balance"] == "0"


@pytest.mark.asyncio
async def test_submit_rejects_wrong_transaction_length(rpc_client):
    response = await rpc_client.post(
        "/v1/transactions",
        headers=auth_headers(),
        json={"raw": "00"},
    )
    assert response.status == 400
    assert (await response.json())["error"] == "invalid_transaction_length"


@pytest.mark.asyncio
async def test_status_exposes_best_peer_height_and_readiness():
    node = MagicMock()
    node.chain.tip = 7
    node.chain.get_block_file_number.return_value = 0
    node.peers = {}
    node.best_peer_height = 12
    node.ready = False
    node.syncing = True
    node.block_sync.syncing = True
    response = await RpcServer(node=node, token=TOKEN)._status(None)
    payload = json.loads(response.text)

    assert payload["height"] == 7
    assert payload["best_peer_height"] == 12
    assert payload["syncing"] is True
    assert payload["ready"] is False


def _accepted_transaction_mock():
    transaction = MagicMock()
    transaction.deserialize.return_value = transaction
    transaction.to_transaction_pool.return_value = True
    transaction.fee = 0
    transaction.value = 1
    transaction.json.return_value = {
        "id": "a" * 64,
        "chain": 1,
        "nonce": 1,
        "fee": 0,
        "value": 1,
        "from_address": KNOWN_ADDRESS,
        "to_address": KNOWN_ADDRESS,
        "unlock_sig": "b" * 256,
    }
    return transaction


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("relay_count", "expected_broadcast"), [(0, False), (2, True)]
)
async def test_submit_reports_real_successful_relay_count(
    relay_count, expected_broadcast
):
    node = MagicMock()
    node.ready = True
    node.broadcast_tx = AsyncMock(return_value=relay_count)
    request = MagicMock()
    request.json = AsyncMock(return_value={"raw": "00" * 213})
    transaction = _accepted_transaction_mock()

    with patch("luracoin.rpc.Transaction", return_value=transaction):
        response = await RpcServer(node=node, token=TOKEN)._submit_transaction(
            request
        )
    payload = json.loads(response.text)

    assert response.status == 202
    assert payload["accepted"] is True
    assert payload["broadcast"] is expected_broadcast
    assert payload["relay_count"] == relay_count
    node.broadcast_tx.assert_awaited_once_with(transaction)


@pytest.mark.asyncio
async def test_submit_rejects_while_node_is_not_ready():
    node = MagicMock()
    node.ready = False
    request = MagicMock()
    request.json = AsyncMock(return_value={"raw": "00" * 213})

    with pytest.raises(web.HTTPServiceUnavailable) as error:
        await RpcServer(node=node, token=TOKEN)._submit_transaction(request)

    assert json.loads(error.value.text)["error"] == "node_not_ready"


@pytest.mark.asyncio
async def test_submit_reports_any_redis_failure_as_service_unavailable():
    request = MagicMock()
    request.json = AsyncMock(return_value={"raw": "00" * 213})
    transaction = _accepted_transaction_mock()
    transaction.to_transaction_pool.side_effect = (
        redis.exceptions.TimeoutError("redis timeout")
    )

    with (
        patch("luracoin.rpc.Transaction", return_value=transaction),
        pytest.raises(web.HTTPServiceUnavailable) as error,
    ):
        await RpcServer(token=TOKEN)._submit_transaction(request)

    assert json.loads(error.value.text)["error"] == "mempool_unavailable"


@pytest.mark.asyncio
async def test_account_history_uses_index_and_returns_cursor():
    transaction = _accepted_transaction_mock()
    transaction.id = "a" * 64
    block = SimpleNamespace(timestamp=1234, txns=[transaction])
    chain = MagicMock()
    chain.get_block_file_number.return_value = 0
    chain.get_account.return_value = {"balance": 9, "nonce": 0}
    chain.get_address_transaction_refs.return_value = (
        [
            {
                "height": 7,
                "index": 0,
                "transaction_id": transaction.id,
                "cursor": "000000070000",
            }
        ],
        "000000070000",
    )
    request = MagicMock()
    request.match_info = {"address": KNOWN_ADDRESS}
    request.query = {"limit": "1"}

    with (
        patch("luracoin.rpc.Chain", return_value=chain),
        patch(
            "luracoin.rpc.Block.get_many", return_value={7: block}
        ) as blocks_get,
        patch(
            "luracoin.rpc._mempool_account_view",
            return_value={"available": True, "transactions": []},
        ),
    ):
        response = await RpcServer(token=TOKEN)._account_transactions(request)

    payload = json.loads(response.text)
    chain.get_address_transaction_refs.assert_called_once_with(
        KNOWN_ADDRESS, limit=1, cursor=None
    )
    assert list(blocks_get.call_args.args[0]) == [7]
    assert payload["transactions"][0]["block_height"] == 7
    assert payload["transactions"][0]["status"] == "confirmed"
    assert payload["next_cursor"] == "000000070000"


@pytest.mark.asyncio
async def test_account_history_rejects_invalid_cursor():
    chain = MagicMock()
    chain.get_block_file_number.return_value = 0
    chain.get_account.return_value = {"balance": 0, "nonce": 0}
    chain.get_address_transaction_refs.side_effect = ValueError("bad cursor")
    request = MagicMock()
    request.match_info = {"address": KNOWN_ADDRESS}
    request.query = {"cursor": "not-hex"}

    with (
        patch("luracoin.rpc.Chain", return_value=chain),
        patch(
            "luracoin.rpc._mempool_account_view",
            return_value={"available": True, "transactions": []},
        ),
        pytest.raises(web.HTTPBadRequest) as error,
    ):
        await RpcServer(token=TOKEN)._account_transactions(request)

    assert json.loads(error.value.text)["error"] == "invalid_cursor"


@pytest.mark.asyncio
async def test_account_history_latest_cursor_skips_pending_first_page():
    chain = MagicMock()
    chain.get_block_file_number.return_value = 0
    chain.get_account.return_value = {"balance": 0, "nonce": 0}
    chain.get_address_transaction_refs.return_value = ([], None)
    request = MagicMock()
    request.match_info = {"address": KNOWN_ADDRESS}
    request.query = {"cursor": "latest"}

    with (
        patch("luracoin.rpc.Chain", return_value=chain),
        patch(
            "luracoin.rpc._mempool_account_view",
            return_value={
                "available": True,
                "transactions": [{"id": "pending"}],
            },
        ),
    ):
        response = await RpcServer(token=TOKEN)._account_transactions(request)

    payload = json.loads(response.text)
    assert payload["transactions"] == []
    chain.get_address_transaction_refs.assert_called_once_with(
        KNOWN_ADDRESS, limit=50, cursor=None
    )
