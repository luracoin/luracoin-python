import asyncio
import sqlite3
import threading
from dataclasses import dataclass

import pytest

from luracoin.explorer_index import (
    SCHEMA_VERSION,
    ExplorerChainDivergence,
    ExplorerIndex,
    ExplorerIndexer,
    ExplorerIndexNotInitialized,
    ExplorerNetworkMismatch,
)
from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.genesis import GENESIS_ADDRESS, initialize_chain

ZERO_ADDRESS = "0" * 34
ADDRESS_A = "L" + "a" * 33
ADDRESS_B = "L" + "b" * 33


@dataclass
class FakeTransaction:
    id: str
    chain: int
    nonce: int
    fee: int
    value: int
    from_address: str
    to_address: str

    @property
    def is_coinbase(self):
        return self.from_address == ZERO_ADDRESS


@dataclass
class FakeBlock:
    id: str
    height: int
    prev_block_hash: str
    miner: str
    timestamp: int
    bits: bytes
    nonce: int
    version: int
    txns: list

    def serialize(self):
        return b"x" * (118 + 213 * len(self.txns))


class FakeBlockSource:
    blocks = {}
    get_many_calls = []

    @classmethod
    def configure(cls, blocks):
        cls.blocks = {block.height: block for block in blocks}
        cls.get_many_calls = []

    @classmethod
    def get_many(cls, heights):
        requested = list(heights)
        cls.get_many_calls.append(requested)
        return {
            height: cls.blocks[height]
            for height in requested
            if height in cls.blocks
        }


class FakeChain:
    @property
    def tip(self):
        return max(FakeBlockSource.blocks, default=0)

    def get_block_file_number(self, height):
        return 0 if height in FakeBlockSource.blocks else None


def _hash(number):
    return f"{number:064x}"


def _coinbase(identifier, receiver, value, nonce):
    return FakeTransaction(
        id=_hash(identifier),
        chain=1,
        nonce=nonce,
        fee=0,
        value=value,
        from_address=ZERO_ADDRESS,
        to_address=receiver,
    )


def _base_blocks():
    large_reward = 2**63 + 1_000
    genesis = FakeBlock(
        id=_hash(100),
        height=0,
        prev_block_hash="0" * 64,
        miner=ADDRESS_A,
        timestamp=1_700_000_000,
        bits=b"\x1d\xff\xff\xff",
        nonce=11,
        version=1,
        txns=[_coinbase(1, ADDRESS_A, large_reward, 0)],
    )
    transfer = FakeTransaction(
        id=_hash(3),
        chain=1,
        nonce=1,
        fee=100,
        value=900,
        from_address=ADDRESS_A,
        to_address=ADDRESS_B,
    )
    second = FakeBlock(
        id=_hash(101),
        height=1,
        prev_block_hash=genesis.id,
        miner=ADDRESS_B,
        timestamp=1_700_000_180,
        bits=b"\x1d\xff\xff\xff",
        nonce=12,
        version=1,
        txns=[_coinbase(2, ADDRESS_B, 50, 1), transfer],
    )
    return [genesis, second]


@pytest.fixture
def fake_chain():
    FakeBlockSource.configure(_base_blocks())
    return FakeChain()


def test_database_is_not_created_until_explicit_initialization(tmp_path):
    path = tmp_path / "not-created" / "explorer.sqlite3"
    index = ExplorerIndex(path, network="testnet", chain_id=1)

    assert not path.exists()
    assert not path.parent.exists()
    with pytest.raises(ExplorerIndexNotInitialized):
        index.list_blocks()
    assert not path.exists()

    index.initialize()
    try:
        assert path.exists()
        assert index.get_metadata() == {
            "schema_version": SCHEMA_VERSION,
            "network": "testnet",
            "chain_id": 1,
            "indexed_height": -1,
            "indexed_block_id": None,
        }
        assert (
            index._connection.execute("PRAGMA journal_mode").fetchone()[0]
            == "wal"
        )
        assert (
            index._connection.execute("PRAGMA busy_timeout").fetchone()[0]
            == 5_000
        )
    finally:
        index.close()


def test_backfill_real_canonical_genesis(tmp_path):
    genesis = initialize_chain()
    index = ExplorerIndex(
        tmp_path / "real-explorer.sqlite3",
        network=Config.NETWORK,
        chain_id=Config.CHAIN_ID,
    ).initialize()
    try:
        assert index.backfill(Chain(), Block) == 1
        assert index.get_metadata()["indexed_block_id"] == genesis.id
        assert index.get_stats()["blocks"] == 1
        address = index.list_addresses(limit=1)["items"][0]
        assert address["address"] == GENESIS_ADDRESS
        assert address["balance"] == str(Config.COINS_TO_FORGE)
    finally:
        index.close()


def test_backfill_uses_batches_and_preserves_unsigned_amounts(
    tmp_path, fake_chain
):
    path = tmp_path / "explorer.sqlite3"
    index = ExplorerIndex(path, network="testnet", chain_id=1).initialize()
    try:
        assert index.backfill(fake_chain, FakeBlockSource, batch_size=1) == 2
        assert FakeBlockSource.get_many_calls == [[0], [1]]

        metadata = index.get_metadata()
        assert metadata["indexed_height"] == 1
        assert metadata["indexed_block_id"] == _hash(101)

        blocks = index.list_blocks(limit=1, offset=0)
        assert blocks["total"] == 2
        assert blocks["items"][0]["height"] == 1
        assert blocks["items"][0]["total_fees"] == "100"

        transactions = index.list_transactions(limit=2, offset=0)
        assert transactions["total"] == 3
        assert [item["id"] for item in transactions["items"]] == [
            _hash(3),
            _hash(2),
        ]
        assert transactions["items"][0]["block_id"] == _hash(101)
        assert transactions["items"][0]["block_timestamp"] == 1_700_000_180
        assert transactions["items"][0]["transaction_index"] == 1
        assert transactions["items"][0]["confirmations"] == 1
        assert transactions["items"][0]["unlock_sig"] is None
        assert all(
            isinstance(item["value"], str) for item in transactions["items"]
        )

        addresses = index.list_addresses(limit=10, offset=0)
        assert addresses["total"] == 2
        assert addresses["items"][0]["address"] == ADDRESS_A
        assert addresses["items"][0]["balance"] == str(2**63)

        history = index.get_address_transactions(ADDRESS_A, limit=1, offset=0)
        assert history["total"] == 2
        assert history["items"][0]["direction"] == "sent"
        assert (
            index.get_address_transactions(ADDRESS_A, limit=1, offset=1)[
                "items"
            ][0]["direction"]
            == "mined"
        )

        stats = index.get_stats()
        assert stats == {
            "network": "testnet",
            "chain_id": 1,
            "indexed_height": 1,
            "indexed_block_id": _hash(101),
            "blocks": 2,
            "transactions": 3,
            "addresses": 2,
            "total_fees": "100",
            "total_transferred": "900",
            "total_rewards": str(2**63 + 1_050),
        }

        with sqlite3.connect(path) as connection:
            value_type, stored = connection.execute(
                """
                SELECT typeof(value), value FROM transactions WHERE id = ?
                """,
                (_hash(1),),
            ).fetchone()
            balance_type = connection.execute(
                "SELECT typeof(balance) FROM addresses WHERE address = ?",
                (ADDRESS_A,),
            ).fetchone()[0]
        assert value_type == "text"
        assert stored == str(2**63 + 1_000)
        assert balance_type == "text"
    finally:
        index.close()


def test_backfill_matches_consensus_transfer_then_coinbase_order(tmp_path):
    maximum_balance = 0xFFFFFFFFFFFFFFFF
    genesis = FakeBlock(
        id=_hash(200),
        height=0,
        prev_block_hash="0" * 64,
        miner=ADDRESS_A,
        timestamp=1_700_000_000,
        bits=b"\x1d\xff\xff\xff",
        nonce=1,
        version=1,
        txns=[_coinbase(20, ADDRESS_A, maximum_balance, 0)],
    )
    transfer = FakeTransaction(
        id=_hash(22),
        chain=1,
        nonce=1,
        fee=0,
        value=100,
        from_address=ADDRESS_A,
        to_address=ADDRESS_B,
    )
    second = FakeBlock(
        id=_hash(201),
        height=1,
        prev_block_hash=genesis.id,
        miner=ADDRESS_A,
        timestamp=1_700_000_180,
        bits=b"\x1d\xff\xff\xff",
        nonce=2,
        version=1,
        txns=[_coinbase(21, ADDRESS_A, 50, 1), transfer],
    )
    FakeBlockSource.configure([genesis, second])
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        assert index.backfill(FakeChain(), FakeBlockSource) == 2
        addresses = {
            item["address"]: item
            for item in index.list_addresses(limit=10)["items"]
        }
        assert addresses[ADDRESS_A]["balance"] == str(maximum_balance - 50)
        assert addresses[ADDRESS_B]["balance"] == "100"
    finally:
        index.close()


def test_stats_hold_one_snapshot_lock(tmp_path, fake_chain, monkeypatch):
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        index.backfill(fake_chain, FakeBlockSource)
        original_get_metadata = index.get_metadata
        competing_lock_results = []

        def get_metadata_while_stats_is_read():
            def try_competing_read():
                acquired = index._connection_lock.acquire(timeout=0.05)
                competing_lock_results.append(acquired)
                if acquired:
                    index._connection_lock.release()

            contender = threading.Thread(target=try_competing_read)
            contender.start()
            contender.join()
            return original_get_metadata()

        monkeypatch.setattr(
            index, "get_metadata", get_metadata_while_stats_is_read
        )
        assert index.get_stats()["indexed_height"] == 1
        assert competing_lock_results == [False]
    finally:
        index.close()


def test_resume_and_repeated_backfill_are_idempotent(tmp_path, fake_chain):
    path = tmp_path / "explorer.sqlite3"
    index = ExplorerIndex(path, network="testnet", chain_id=1).initialize()
    try:
        assert index.backfill(fake_chain, FakeBlockSource) == 2
        first_stats = index.get_stats()
        assert index.backfill(fake_chain, FakeBlockSource) == 0
        assert index.get_stats() == first_stats

        previous = FakeBlockSource.blocks[1]
        third = FakeBlock(
            id=_hash(102),
            height=2,
            prev_block_hash=previous.id,
            miner=ADDRESS_A,
            timestamp=1_700_000_360,
            bits=b"\x1d\xff\xff\xff",
            nonce=13,
            version=1,
            txns=[_coinbase(4, ADDRESS_A, 25, 2)],
        )
        FakeBlockSource.blocks[2] = third

        assert index.backfill(fake_chain, FakeBlockSource) == 1
        assert index.backfill(fake_chain, FakeBlockSource) == 0
        assert index.get_stats()["blocks"] == 3
        assert index.get_stats()["transactions"] == 4
        assert index.list_blocks(limit=10, offset=0)["total"] == 3
    finally:
        index.close()

    reopened = ExplorerIndex(path, network="testnet", chain_id=1).initialize()
    try:
        assert reopened.backfill(fake_chain, FakeBlockSource) == 0
        assert reopened.get_metadata()["indexed_height"] == 2
    finally:
        reopened.close()


def test_backfill_can_stop_cleanly_between_batches(tmp_path, fake_chain):
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        indexed = index.backfill(
            fake_chain,
            FakeBlockSource,
            batch_size=1,
            stop_requested=lambda: (
                index.get_metadata()["indexed_height"] >= 0
            ),
        )

        assert indexed == 1
        assert index.get_metadata()["indexed_height"] == 0
        assert index.backfill(fake_chain, FakeBlockSource) == 1
    finally:
        index.close()


def test_rejects_reusing_database_for_another_network(tmp_path):
    path = tmp_path / "explorer.sqlite3"
    original = ExplorerIndex(path, network="testnet", chain_id=1).initialize()
    original.close()

    incompatible = ExplorerIndex(path, network="devnet", chain_id=2)
    with pytest.raises(ExplorerNetworkMismatch):
        incompatible.initialize()
    assert not incompatible.initialized


def test_hash_divergence_rebuilds_all_derived_rows(tmp_path, fake_chain):
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        assert index.backfill(fake_chain, FakeBlockSource) == 2
        genesis = FakeBlockSource.blocks[0]
        replacement = FakeBlock(
            id=_hash(999),
            height=1,
            prev_block_hash=genesis.id,
            miner=ADDRESS_A,
            timestamp=1_700_000_181,
            bits=b"\x1d\xff\xff\xff",
            nonce=99,
            version=1,
            txns=[_coinbase(99, ADDRESS_A, 75, 1)],
        )
        FakeBlockSource.configure([genesis, replacement])

        assert index.backfill(fake_chain, FakeBlockSource, batch_size=1) == 2
        assert index.get_metadata()["indexed_block_id"] == replacement.id
        assert index.list_transactions(limit=10, offset=0)["total"] == 2
        assert index.get_stats()["total_fees"] == "0"
        assert index.get_stats()["total_rewards"] == str(2**63 + 1_075)
    finally:
        index.close()


def test_missing_next_block_preserves_the_valid_indexed_prefix(
    tmp_path, fake_chain
):
    class ChainClaimingOneMoreBlock(FakeChain):
        @property
        def tip(self):
            return 2

    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        assert index.backfill(fake_chain, FakeBlockSource) == 2
        metadata = index.get_metadata()
        stats = index.get_stats()

        for _attempt in range(2):
            with pytest.raises(
                ExplorerChainDivergence, match="canonical block 2 is missing"
            ):
                index.backfill(ChainClaimingOneMoreBlock(), FakeBlockSource)
            assert index.get_metadata() == metadata
            assert index.get_stats() == stats
    finally:
        index.close()


def test_stop_request_rolls_back_the_in_progress_block(tmp_path, fake_chain):
    checks = 0

    def stop_requested():
        nonlocal checks
        checks += 1
        return checks >= 4

    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    try:
        assert (
            index.backfill(
                fake_chain,
                FakeBlockSource,
                stop_requested=stop_requested,
            )
            == 0
        )
        assert index.get_metadata()["indexed_height"] == -1
        assert index.get_stats()["blocks"] == 0
        assert index.backfill(fake_chain, FakeBlockSource) == 2
    finally:
        index.close()


@pytest.mark.asyncio
async def test_async_indexer_follows_without_implicit_initialization(
    tmp_path, fake_chain
):
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    )
    follower = ExplorerIndexer(
        index,
        chain=fake_chain,
        block_cls=FakeBlockSource,
        batch_size=1,
        poll_interval=0.01,
    )

    with pytest.raises(ExplorerIndexNotInitialized):
        await follower.start()
    assert not index.path.exists()

    index.initialize()
    try:
        assert await follower.run_once() == 2
        assert await follower.run_once() == 0
        assert follower.last_error is None
    finally:
        await follower.stop()
        index.close()


@pytest.mark.asyncio
async def test_async_indexer_polling_start_and_stop(tmp_path, fake_chain):
    index = ExplorerIndex(
        tmp_path / "explorer.sqlite3", network="testnet", chain_id=1
    ).initialize()
    follower = ExplorerIndexer(
        index,
        chain=fake_chain,
        block_cls=FakeBlockSource,
        batch_size=1,
        poll_interval=0.01,
    )

    try:
        await follower.start()

        async def wait_until_indexed():
            while index.get_metadata()["indexed_height"] < 1:
                await asyncio.sleep(0.001)

        await asyncio.wait_for(wait_until_indexed(), timeout=1)
        assert follower.running is True
    finally:
        await follower.stop()
        index.close()

    assert follower.running is False
