import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

import luracoin.explorer_api as explorer_api
from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.explorer_api import ExplorerApiServer, create_explorer_app
from luracoin.explorer_index import ExplorerIndex
from luracoin.genesis import initialize_chain

KNOWN_ADDRESS = "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"
ZERO_ADDRESS = "0" * 34


def _hash(number):
    return f"{number:064x}"


class FakeTransaction:
    def __init__(self, number, *, coinbase=False):
        self.id = _hash(number)
        self.chain = 1
        self.nonce = number
        self.fee = 0 if coinbase else number + 10
        self.value = 2**63 + number
        self.from_address = ZERO_ADDRESS if coinbase else KNOWN_ADDRESS
        self.to_address = KNOWN_ADDRESS
        self.unlock_sig = b"signature"

    @property
    def is_coinbase(self):
        return self.from_address == ZERO_ADDRESS

    def json(self):
        return {
            "id": self.id,
            "chain": self.chain,
            "nonce": self.nonce,
            "fee": self.fee,
            "value": self.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "unlock_sig": self.unlock_sig.hex(),
        }


class FakeBlock:
    def __init__(self, height):
        self.height = height
        self.id = _hash(1_000 + height)
        self.prev_block_hash = "0" * 64 if height == 0 else _hash(999 + height)
        self.miner = KNOWN_ADDRESS
        self.timestamp = 1_700_000_000 + height
        self.bits = b"\x1d\xff\xff\xff"
        self.nonce = height + 20
        self.version = 1
        self.txns = [
            FakeTransaction(height * 10 + 1, coinbase=True),
            FakeTransaction(height * 10 + 2),
        ]

    def header(self):
        return {
            "height": self.height,
            "prev_block_hash": self.prev_block_hash,
            "miner": self.miner,
            "id": self.id,
            "nonce": self.nonce,
            "version": self.version,
            "timestamp": self.timestamp,
            "bits": self.bits.hex(),
        }

    def json(self):
        return {
            **self.header(),
            "txns": [transaction.json() for transaction in self.txns],
        }

    def serialize(self):
        return b"b" * (118 + len(self.txns) * 213)


class FakeChain:
    def __init__(self, blocks):
        self.blocks = {block.height: block for block in blocks}

    @property
    def tip(self):
        return max(self.blocks, default=0)

    def get_block_file_number(self, height):
        if height == 0 and self.blocks:
            return 0
        return None

    def get_block_height(self, block_id):
        for height, block in self.blocks.items():
            if block.id == block_id.lower():
                return height
        return None

    def get_transaction_location(self, transaction_id):
        for height, block in self.blocks.items():
            for index, transaction in enumerate(block.txns):
                if transaction.id == transaction_id.lower():
                    return height, index
        return None

    def get_account(self, address):
        if address == KNOWN_ADDRESS:
            return {"balance": 2**63 + 99, "nonce": 7}
        return None


@pytest.fixture
def fake_node(monkeypatch):
    blocks = [FakeBlock(height) for height in range(4)]
    chain = FakeChain(blocks)
    block_get_calls = []

    def get(height):
        block_get_calls.append(height)
        return chain.blocks.get(height)

    def get_many(heights):
        requested = list(heights)
        return {
            height: chain.blocks[height]
            for height in requested
            if height in chain.blocks
        }

    monkeypatch.setattr(
        explorer_api.Block,
        "get",
        staticmethod(get),
    )
    monkeypatch.setattr(
        explorer_api.Block,
        "get_many",
        staticmethod(get_many),
    )
    node = SimpleNamespace(
        chain=chain,
        ready=True,
        syncing=False,
        peers={"private-peer": object()},
        rpc_token="do-not-expose",
        data_dir="/private/node/data",
    )
    return node, blocks, block_get_calls


@asynccontextmanager
async def _client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://explorer.test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_public_service_metadata_docs_and_cors(fake_node):
    node, blocks, _calls = fake_node
    app = create_explorer_app(node=node)

    async with _client(app) as client:
        health = await client.get(
            "/health", headers={"Origin": "https://explorer.example"}
        )
        status = await client.get("/api/v1/status")
        features = await client.get("/api/v1/features")
        docs = await client.get("/docs")
        schema = await client.get("/openapi.json")

    assert health.status_code == 200
    assert health.headers["access-control-allow-origin"] == "*"
    assert docs.status_code == 200
    assert schema.status_code == 200
    assert status.json()["tip_id"] == blocks[-1].id
    assert status.json()["index"] == {
        "enabled": False,
        "ready": False,
        "state": "disabled",
    }
    assert status.json()["capabilities"]["block_list"] is True
    assert status.json()["capabilities"]["transaction_feed"] is False
    assert features.json()["features"]["explorer_index"]["state"] == (
        "disabled"
    )
    paths = schema.json()["paths"]
    assert "/api/v1/transactions/{txid}" in paths
    assert "/api/v1/blocks/{block_ref}/transactions" in paths
    transaction_schema = schema.json()["components"]["schemas"][
        "ExplorerTransaction"
    ]
    assert transaction_schema["properties"]["fee"]["type"] == "string"
    assert "transaction_index" in transaction_schema["required"]
    block_schema = schema.json()["components"]["schemas"]["BlockSummary"]
    assert "txns" not in block_schema["properties"]

    public_json = json.dumps(
        [health.json(), status.json(), features.json()], sort_keys=True
    )
    for secret in ("do-not-expose", "/private/node/data", "private-peer"):
        assert secret not in public_json


@pytest.mark.asyncio
async def test_core_block_listing_uses_canonical_store(fake_node):
    node, _blocks, calls = fake_node
    app = create_explorer_app(node=node)

    async with _client(app) as client:
        newest = await client.get("/api/v1/blocks?limit=2")
        offset = await client.get("/api/v1/blocks?limit=2&offset=1")
        cursor = await client.get("/api/v1/blocks?limit=2&before_height=2")

    assert newest.status_code == 200
    assert [item["height"] for item in newest.json()["items"]] == [3, 2]
    assert newest.json()["items"][0]["size_bytes"] == 544
    assert newest.json()["items"][0]["total_fees"] == "42"
    assert newest.json()["items"][0]["reward"] == str(2**63 + 31)
    assert newest.json()["pagination"] == {
        "limit": 2,
        "offset": 0,
        "count": 2,
        "total": 4,
        "before_height": None,
        "next_before_height": 2,
    }
    assert [item["height"] for item in offset.json()["items"]] == [2, 1]
    assert [item["height"] for item in cursor.json()["items"]] == [1, 0]
    assert calls == [3, 2, 2, 1, 1, 0]


@pytest.mark.asyncio
async def test_core_block_and_transaction_lookups(fake_node):
    node, blocks, _calls = fake_node
    block = blocks[2]
    transaction = block.txns[1]
    app = create_explorer_app(node=node)

    async with _client(app) as client:
        by_height = await client.get(f"/api/v1/blocks/{block.height}")
        by_hash = await client.get(f"/api/v1/blocks/{block.id.upper()}")
        transaction_response = await client.get(
            f"/api/v1/transactions/{transaction.id.upper()}"
        )
        block_transactions = await client.get(
            f"/api/v1/blocks/{block.height}/transactions?limit=1&offset=1"
        )
        invalid_block = await client.get("/api/v1/blocks/not-a-block")
        missing_block = await client.get(f"/api/v1/blocks/{'f' * 64}")
        invalid_transaction = await client.get(
            "/api/v1/transactions/not-a-transaction"
        )
        missing_transaction = await client.get(
            f"/api/v1/transactions/{'f' * 64}"
        )

    assert by_height.status_code == by_hash.status_code == 200
    assert by_height.json()["block"]["id"] == block.id
    assert by_height.json()["block"]["confirmations"] == 2
    assert by_height.json()["block"]["transaction_count"] == 2
    assert "txns" not in by_height.json()["block"]
    assert transaction_response.status_code == 200
    payload = transaction_response.json()["transaction"]
    assert payload["id"] == transaction.id
    assert payload["block_height"] == 2
    assert payload["transaction_index"] == 1
    assert payload["fee"] == "32"
    assert block_transactions.status_code == 200
    assert block_transactions.json()["items"][0]["id"] == transaction.id
    assert block_transactions.json()["items"][0]["fee"] == "32"
    assert block_transactions.json()["items"][0]["value"] == str(2**63 + 22)
    assert block_transactions.json()["pagination"]["total"] == 2
    assert invalid_block.json()["error"] == "invalid_block_reference"
    assert missing_block.json()["error"] == "block_not_found"
    assert invalid_transaction.json()["error"] == "invalid_transaction_id"
    assert missing_transaction.json()["error"] == "transaction_not_found"


@pytest.mark.asyncio
async def test_core_address_state_is_string_safe(fake_node):
    node, _blocks, _calls = fake_node
    app = create_explorer_app(node=node)

    async with _client(app) as client:
        known = await client.get(f"/api/v1/addresses/{KNOWN_ADDRESS}")
        invalid = await client.get("/api/v1/addresses/not-an-address")

    assert known.status_code == 200
    assert known.json() == {
        "network": explorer_api.Config.NETWORK,
        "address": KNOWN_ADDRESS,
        "exists": True,
        "balance": str(2**63 + 99),
        "nonce": 7,
    }
    assert invalid.status_code == 400
    assert invalid.json()["error"] == "invalid_address"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/transactions",
        "/api/v1/addresses",
        f"/api/v1/addresses/{KNOWN_ADDRESS}/transactions",
        "/api/v1/stats",
    ],
)
async def test_indexed_routes_have_stable_disabled_response(fake_node, path):
    node, _blocks, _calls = fake_node
    async with _client(create_explorer_app(node=node)) as client:
        response = await client.get(path)

    assert response.status_code == 503
    assert response.json() == {
        "error": "explorer_index_disabled",
        "index": {
            "enabled": False,
            "ready": False,
            "state": "disabled",
        },
    }


class ReadyIndex:
    def __init__(self):
        self.calls = []

    def list_transactions(self, limit, offset):
        self.calls.append(("transactions", limit, offset))
        return {
            "items": [self._transaction(7, fee=9, value=2**63)],
            "total": 11,
        }

    def list_addresses(self, limit, offset):
        self.calls.append(("addresses", limit, offset))
        return {
            "items": [
                {
                    "address": KNOWN_ADDRESS,
                    "balance": 2**63,
                    "nonce": 7,
                    "total_received": 2**63,
                    "total_sent": 0,
                    "total_fees": 0,
                    "transaction_count": 1,
                    "first_seen_height": 0,
                    "last_seen_height": 3,
                }
            ],
            "total": 1,
        }

    def get_address_transactions(self, address, limit, offset):
        self.calls.append(("history", address, limit, offset))
        return {
            "items": [
                {
                    **self._transaction(8, fee=3, value=4),
                    "direction": "received",
                }
            ],
            "total": 1,
        }

    def get_stats(self):
        self.calls.append(("stats",))
        return {
            "network": explorer_api.Config.NETWORK,
            "chain_id": explorer_api.Config.CHAIN_ID,
            "indexed_height": 3,
            "indexed_block_id": _hash(1_003),
            "blocks": 4,
            "transactions": 8,
            "addresses": 2,
            "total_fees": 12,
            "total_rewards": 2**63,
            "total_transferred": 99,
        }

    @staticmethod
    def _transaction(number, *, fee, value):
        return {
            "id": _hash(number),
            "chain": 1,
            "nonce": number,
            "fee": fee,
            "value": value,
            "from_address": KNOWN_ADDRESS,
            "to_address": KNOWN_ADDRESS,
            "unlock_sig": None,
            "block_height": 3,
            "block_id": _hash(1_003),
            "block_timestamp": 1_700_000_003,
            "transaction_index": 0,
            "confirmations": 1,
            "is_coinbase": False,
        }


class StatusIndexer:
    def __init__(self, status):
        self._status = status

    def status(self):
        return self._status


@pytest.mark.asyncio
async def test_ready_index_routes_and_monetary_strings(fake_node):
    node, _blocks, _calls = fake_node
    index = ReadyIndex()
    indexer = StatusIndexer(
        {
            "state": "ready",
            "ready": True,
            "indexed_height": 3,
            "target_height": 3,
            "progress": 100,
        }
    )
    app = create_explorer_app(node=node, index=index, indexer=indexer)

    async with _client(app) as client:
        transactions = await client.get(
            "/api/v1/transactions?limit=5&offset=2"
        )
        addresses = await client.get("/api/v1/addresses?limit=3")
        history = await client.get(
            f"/api/v1/addresses/{KNOWN_ADDRESS}/transactions?limit=4"
        )
        stats = await client.get("/api/v1/stats")

    assert transactions.status_code == 200
    assert transactions.json()["items"][0]["fee"] == "9"
    assert transactions.json()["items"][0]["value"] == str(2**63)
    assert transactions.json()["pagination"]["total"] == 11
    assert addresses.json()["items"][0]["balance"] == str(2**63)
    assert history.json()["items"][0]["fee"] == "3"
    assert stats.json()["stats"]["total_fees"] == "12"
    assert stats.json()["stats"]["total_rewards"] == str(2**63)
    assert stats.json()["stats"]["total_transferred"] == "99"
    assert index.calls == [
        ("transactions", 5, 2),
        ("addresses", 3, 0),
        ("history", KNOWN_ADDRESS, 4, 0),
        ("stats",),
    ]


@pytest.mark.asyncio
async def test_real_genesis_index_round_trips_through_api(tmp_path):
    genesis = initialize_chain()
    chain = Chain()
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3",
        network=Config.NETWORK,
        chain_id=Config.CHAIN_ID,
    ).initialize()
    index.backfill(chain, Block)
    node = SimpleNamespace(chain=chain, ready=True, syncing=False)

    try:
        async with _client(
            create_explorer_app(node=node, index=index)
        ) as client:
            blocks = await client.get("/api/v1/blocks")
            transactions = await client.get("/api/v1/transactions")
            addresses = await client.get("/api/v1/addresses")
            history = await client.get(
                f"/api/v1/addresses/{KNOWN_ADDRESS}/transactions"
            )
            stats = await client.get("/api/v1/stats")

        assert blocks.json()["items"][0]["id"] == genesis.id
        assert transactions.json()["items"][0]["value"] == str(
            Config.COINS_TO_FORGE
        )
        assert transactions.json()["items"][0]["block_id"] == genesis.id
        assert transactions.json()["items"][0]["transaction_index"] == 0
        assert transactions.json()["items"][0]["confirmations"] == 1
        assert addresses.json()["items"][0]["balance"] == str(
            Config.COINS_TO_FORGE
        )
        assert history.json()["items"][0]["direction"] == "mined"
        assert stats.json()["stats"]["blocks"] == 1
    finally:
        index.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (
            {
                "state": "building",
                "ready": False,
                "indexed_height": 1,
                "target_height": 4,
                "progress": 40,
            },
            "explorer_index_building",
        ),
        (
            {
                "state": "error",
                "ready": False,
                "indexed_height": 1,
                "target_height": 4,
                "progress": 40,
            },
            "explorer_index_error",
        ),
    ],
)
async def test_indexed_routes_block_building_and_error(
    fake_node, status, error
):
    node, _blocks, _calls = fake_node
    app = create_explorer_app(
        node=node,
        index=ReadyIndex(),
        indexer=StatusIndexer(status),
    )

    async with _client(app) as client:
        response = await client.get("/api/v1/transactions")

    assert response.status_code == 503
    assert response.json()["error"] == error
    assert response.json()["index"] == {
        "enabled": True,
        "ready": False,
        "state": status["state"],
        "indexed_height": 1,
        "target_height": 4,
        "progress": 40,
    }


@pytest.mark.asyncio
async def test_index_status_is_derived_for_current_indexer_contract(fake_node):
    node, _blocks, _calls = fake_node

    class MetadataIndex(ReadyIndex):
        def get_metadata(self):
            return {"indexed_height": 1}

    indexer = SimpleNamespace(chain=node.chain, last_error=None)
    app = create_explorer_app(
        node=node, index=MetadataIndex(), indexer=indexer
    )

    async with _client(app) as client:
        status = await client.get("/api/v1/status")
        blocked = await client.get("/api/v1/transactions")

    assert status.json()["index"] == {
        "enabled": True,
        "ready": False,
        "state": "building",
        "indexed_height": 1,
        "target_height": 3,
        "progress": 50.0,
    }
    assert blocked.status_code == 503
    assert blocked.json()["error"] == "explorer_index_building"


@pytest.mark.asyncio
async def test_pagination_is_bounded_by_fastapi(fake_node):
    node, _blocks, _calls = fake_node
    app = create_explorer_app(node=node)

    async with _client(app) as client:
        too_large = await client.get("/api/v1/blocks?limit=11")
        negative = await client.get("/api/v1/blocks?offset=-1")

    assert too_large.status_code == 422
    assert negative.status_code == 422


class FakeUvicornServer:
    def __init__(self, config):
        self.config = config
        self.started = False
        self.should_exit = False
        self.force_exit = False

    async def serve(self):
        self.started = True
        while not self.should_exit and not self.force_exit:
            await asyncio.sleep(0)
        self.started = False


@pytest.mark.asyncio
async def test_embedded_server_start_stop_is_idempotent(
    monkeypatch, fake_node
):
    node, _blocks, _calls = fake_node
    monkeypatch.setattr(
        explorer_api, "_EmbeddedUvicornServer", FakeUvicornServer
    )
    server = ExplorerApiServer(node=node, host="127.0.0.1", port=18000)

    assert server.host == "127.0.0.1"
    assert server.port == 18000
    assert server.index_enabled is False
    await server.start()
    await server.start()
    assert server.started is True
    await server.stop()
    await server.stop()
    assert server.started is False

    await server.start()
    assert server.started is True
    await server.stop()


@pytest.mark.asyncio
async def test_real_embedded_server_serves_health(fake_node, unused_tcp_port):
    node, _blocks, _calls = fake_node
    server = ExplorerApiServer(
        node=node, host="127.0.0.1", port=unused_tcp_port
    )

    try:
        await server.start()
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{unused_tcp_port}",
            trust_env=False,
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["ok"] is True
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_server_owns_opt_in_index_lifecycle(
    monkeypatch, fake_node, tmp_path
):
    node, _blocks, _calls = fake_node
    events = []

    class FakeIndex:
        def __init__(self, path, *, network, chain_id):
            events.append(("construct", str(path), network, chain_id))

        def initialize(self):
            events.append(("initialize",))

        def close(self):
            events.append(("close",))

    class FakeIndexer:
        def __init__(self, index, *, chain, block_cls, poll_interval):
            events.append(("indexer", index, chain, block_cls, poll_interval))

        async def start(self):
            events.append(("start",))

        async def stop(self):
            events.append(("stop",))

    import luracoin.explorer_index as explorer_index

    monkeypatch.setattr(explorer_index, "ExplorerIndex", FakeIndex)
    monkeypatch.setattr(explorer_index, "ExplorerIndexer", FakeIndexer)
    monkeypatch.setattr(
        explorer_api, "_EmbeddedUvicornServer", FakeUvicornServer
    )
    path = tmp_path / "explorer.sqlite3"
    server = ExplorerApiServer(
        node=node,
        index_enabled=True,
        index_path=str(path),
        poll_interval=0.25,
    )

    assert events == []
    assert not path.exists()
    await server.start()
    owned_index = server.index
    owned_indexer = server.indexer
    await server.stop()

    assert events[0][:2] == ("construct", str(path))
    assert ("initialize",) in events
    assert ("start",) in events
    assert ("stop",) in events
    assert ("close",) in events
    assert events[2][1] is owned_index
    assert owned_indexer is not None
    assert server.index is None
    assert server.indexer is None
    assert not path.exists()
