import threading
from unittest.mock import patch

import pytest

from luracoin import blocks as blocks_module
from luracoin.blocks import Block
from luracoin.chain import Chain, blk_file_format
from luracoin.exceptions import BlockNotValidError
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def _save_block(height=0, prev_hash=None, timestamp=None):
    if height == 0:
        return initialize_chain()

    previous = Block.get(height - 1)
    assert previous is not None
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=height,
        fee=0,
        value=mining_reward(height),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=height,
        miner=WALLET_1["address"],
        prev_block_hash=prev_hash or previous.id,
        timestamp=timestamp or previous.timestamp + 1,
        bits=Block.expected_bits(height),
        nonce=0,
        txns=[coinbase],
    )
    with patch.object(Block, "is_valid_proof", return_value=True):
        block.save()
    return block


def _build_next_block(previous):
    height = previous.height + 1
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=height,
        fee=0,
        value=mining_reward(height),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    return Block(
        version=1,
        height=height,
        miner=WALLET_1["address"],
        prev_block_hash=previous.id,
        timestamp=previous.timestamp + 1,
        bits=Block.expected_bits(height),
        nonce=0,
        txns=[coinbase],
    )


def test_block_last_returns_last_saved_block():
    block0 = _save_block(height=0)
    block1 = _save_block(
        height=1, prev_hash=block0.id, timestamp=1_623_168_500
    )

    last = Block.last()
    assert last.height == 1
    assert last.id == block1.id


def test_block_get_returns_none_for_nonexistent_height():
    assert Block.get(999) is None


def test_block_get_returns_correct_block():
    block0 = _save_block(height=0)
    retrieved = Block.get(0)
    assert retrieved is not None
    assert retrieved.id == block0.id
    assert retrieved.height == 0


def test_block_get_many_reads_only_precise_indexed_records():
    block0 = _save_block(height=0)
    block1 = _save_block(height=1, prev_hash=block0.id)
    original_reader = Block._read_block_at_location

    with patch.object(
        Block,
        "_read_block_at_location",
        wraps=original_reader,
    ) as reader:
        retrieved = Block.get_many([0, 1, 1])

    assert retrieved[0].id == block0.id
    assert retrieved[1].id == block1.id
    assert reader.call_count == 2


def test_legacy_v2_file_indexes_are_scanned_once_and_upgraded():
    block0 = _save_block(height=0)
    block1 = _save_block(height=1, prev_hash=block0.id)
    chain = Chain()
    chain.set_block_file_number(0, 0)
    chain.set_block_file_number(1, 0)
    original_reader = Block._get_block_records_from_file

    with patch.object(
        Block,
        "_get_block_records_from_file",
        wraps=original_reader,
    ) as reader:
        retrieved = Block.get_many([0])

    assert retrieved[0].id == block0.id
    reader.assert_called_once_with(0)
    assert chain.get_block_location(0)[1:] == (0, len(block0.serialize()))
    assert chain.get_block_location(1)[1:] == (
        len(block0.serialize()) + 4,
        len(block1.serialize()),
    )

    with patch.object(
        Block,
        "_get_block_records_from_file",
        side_effect=AssertionError("legacy block file was rescanned"),
    ):
        assert Block.get(1).id == block1.id


def test_precise_block_read_fails_closed_on_truncated_record():
    _save_block(height=0)
    file_number, offset, length = Chain().get_block_location(0)
    path = Config.BLOCKS_DIR + f"blk{blk_file_format(file_number)}.dat"
    with open(path, "r+b") as stream:
        stream.truncate(offset + 4 + length - 1)

    with pytest.raises(BlockNotValidError, match="record is truncated"):
        Block.get(0)


def test_precise_block_read_rejects_prefix_before_reading_payload():
    _save_block(height=0)
    file_number, offset, length = Chain().get_block_location(0)
    path = Config.BLOCKS_DIR + f"blk{blk_file_format(file_number)}.dat"
    with open(path, "r+b") as stream:
        stream.seek(offset)
        stream.write((length + 213).to_bytes(4, byteorder="little"))

    with pytest.raises(BlockNotValidError, match="length does not match"):
        Block.get(0)


def test_precise_block_read_uses_the_append_lock():
    block = _save_block(height=0)
    started = threading.Event()
    finished = threading.Event()
    result = []

    def read_block():
        started.set()
        result.append(Block.get(0))
        finished.set()

    with blocks_module._block_file_lock:
        reader = threading.Thread(target=read_block)
        reader.start()
        assert started.wait(timeout=1)
        assert not finished.wait(timeout=0.05)

    reader.join(timeout=1)
    assert not reader.is_alive()
    assert result[0].id == block.id


def test_new_block_save_does_not_scan_historical_block_files():
    block0 = _save_block(height=0)

    with patch.object(
        Block,
        "_get_block_records_from_file",
        side_effect=AssertionError("new save scanned chain history"),
    ):
        block1 = _save_block(height=1, prev_hash=block0.id)

    assert Block.get(1).id == block1.id


def test_interrupted_append_recovers_from_next_file_without_scan(monkeypatch):
    block0 = _save_block(height=0)
    block1 = _build_next_block(block0)
    monkeypatch.setattr(Config, "MAX_FILE_SIZE", len(block0.serialize()) + 4)

    with (
        patch.object(Block, "is_valid_proof", return_value=True),
        patch.object(
            Block,
            "apply_account_updates",
            side_effect=RuntimeError("simulated crash"),
        ),
    ):
        with pytest.raises(RuntimeError, match="simulated crash"):
            block1.save()

    with (
        patch.object(Block, "is_valid_proof", return_value=True),
        patch.object(
            Block,
            "_get_block_records_from_file",
            side_effect=AssertionError("recovery scanned chain history"),
        ),
    ):
        block1.save()

    assert Chain().get_block_location(1) == (
        1,
        0,
        len(block1.serialize()),
    )
    assert len(Block.get_blocks_from_file(1)) == 1


def test_unindexed_recovery_rejects_bytes_after_candidate():
    block0 = _save_block(height=0)
    block1 = _build_next_block(block0)
    Block._append_record(0, block1.serialize())
    path = Config.BLOCKS_DIR + f"blk{blk_file_format(0)}.dat"
    with open(path, "ab") as stream:
        stream.write(b"\x00")

    with patch.object(Block, "is_valid_proof", return_value=True):
        with pytest.raises(BlockNotValidError, match="not the file tail"):
            block1.save()


def test_block_header_contains_all_fields():
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=mining_reward(0),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=Config.STARTING_DIFFICULTY,
        nonce=42,
        txns=[coinbase],
    )

    header = block.header()
    assert header["height"] == 0
    assert header["prev_block_hash"] == "0" * 64
    assert header["miner"] == WALLET_1["address"]
    assert header["nonce"] == 42
    assert header["version"] == 1
    assert header["timestamp"] == 1_623_168_442
    assert header["bits"] == Config.STARTING_DIFFICULTY.hex()
    assert header["id"] == block.id


def test_block_json_includes_header_and_txns():
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=mining_reward(0),
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=Config.STARTING_DIFFICULTY,
        nonce=0,
        txns=[coinbase],
    )

    j = block.json()
    assert "txns" in j
    assert len(j["txns"]) == 1
    assert j["txns"][0]["value"] == mining_reward(0)
    assert j["height"] == 0
    assert j["version"] == 1


def test_block_id_is_deterministic():
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=50000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=Config.STARTING_DIFFICULTY,
        nonce=0,
        txns=[coinbase],
    )

    assert block.id == block.id
    assert len(block.id) == 64


def test_block_id_changes_with_nonce():
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=50000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block1 = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=Config.STARTING_DIFFICULTY,
        nonce=0,
        txns=[coinbase],
    )

    block2 = Block(
        version=1,
        height=0,
        miner=WALLET_1["address"],
        prev_block_hash="0" * 64,
        timestamp=1_623_168_442,
        bits=Config.STARTING_DIFFICULTY,
        nonce=1,
        txns=[coinbase],
    )

    assert block1.id != block2.id
