from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def _save_block(height=0, prev_hash=None, timestamp=1_623_168_442):
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(height),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=height, miner=WALLET_1["address"],
        prev_block_hash=prev_hash or "0" * 64,
        timestamp=timestamp, bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )
    block.save()
    return block


def test_block_last_returns_last_saved_block():
    block0 = _save_block(height=0)
    block1 = _save_block(height=1, prev_hash=block0.id, timestamp=1_623_168_500)

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


def test_block_header_contains_all_fields():
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=42,
        txns=[coinbase],
    )

    header = block.header()
    assert header["height"] == 0
    assert header["prev_block_hash"] == "0" * 64
    assert header["miner"] == WALLET_1["address"]
    assert header["nonce"] == 42
    assert header["version"] == 1
    assert header["timestamp"] == 1_623_168_442
    assert header["bits"] == "1f00ffff"
    assert header["id"] == block.id


def test_block_json_includes_header_and_txns():
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
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
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    assert block.id == block.id
    assert len(block.id) == 64


def test_block_id_changes_with_nonce():
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block1 = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0,
        txns=[coinbase],
    )

    block2 = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=1,
        txns=[coinbase],
    )

    assert block1.id != block2.id
