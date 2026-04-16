import asyncio
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from luracoin.network.miner import MiningNode
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


# ---------------------------------------------------------------------------
# MiningNode construction
# ---------------------------------------------------------------------------

def test_mining_node_creation():
    node = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    assert node.address == WALLET_1["address"]
    assert node.node.port == 19999
    assert node._running is False


# ---------------------------------------------------------------------------
# _build_block_template
# ---------------------------------------------------------------------------

def test_build_block_template_first_block():
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    block = miner._build_block_template()

    assert block is not None
    assert block.height == 0
    assert block.prev_block_hash == "0" * 64
    assert block.version == 1
    assert block.miner == WALLET_1["address"]
    assert len(block.txns) >= 1
    assert block.txns[0].is_coinbase is True
    assert block.txns[0].value == mining_reward(0)
    assert block.txns[0].to_address == WALLET_1["address"]


def test_build_block_template_after_genesis():
    chain = Chain()

    # Save a genesis block
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    genesis = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )
    genesis.save()

    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    block = miner._build_block_template()

    assert block.height == 1
    assert block.prev_block_hash == genesis.id


# ---------------------------------------------------------------------------
# _mine_block (interruptible PoW)
# ---------------------------------------------------------------------------

def test_mine_block_succeeds():
    """PoW with easy difficulty should succeed."""
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    block = miner._build_block_template()
    block.bits = b"\x1f\x00\xff\xff"  # easy

    nonce = miner._mine_block(block)
    assert nonce >= 0
    assert block.is_valid_proof()


def test_mine_block_interrupted():
    """Setting stop event should interrupt mining."""
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    block = miner._build_block_template()
    block.bits = b"\x14\x00\xff\xff"  # hard difficulty

    miner._stop_mining_event.set()
    nonce = miner._mine_block(block)
    assert nonce == -1


# ---------------------------------------------------------------------------
# _on_peer_block callback
# ---------------------------------------------------------------------------

def test_on_peer_block_sets_stop_event():
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    assert not miner._stop_mining_event.is_set()

    miner._on_peer_block()
    assert miner._stop_mining_event.is_set()


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_sets_running_false():
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    miner._running = True
    miner.node.stop = AsyncMock()

    await miner.stop()

    assert miner._running is False
    assert miner._stop_mining_event.is_set()
    miner.node.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Node callback integration
# ---------------------------------------------------------------------------

def test_node_on_new_block_callback_is_set_on_start():
    """After constructing MiningNode, on_new_block should be None.
    It gets set during start(), but we can test the wiring manually."""
    miner = MiningNode(address=WALLET_1["address"], port=19999, seed_nodes=[])
    # Simulate what start() does
    miner.node.on_new_block = miner._on_peer_block

    assert miner.node.on_new_block is not None
    miner.node.on_new_block()
    assert miner._stop_mining_event.is_set()


# ---------------------------------------------------------------------------
# Node._handle_block calls on_new_block
# ---------------------------------------------------------------------------

def test_node_handle_block_triggers_callback():
    """When node receives a valid block, on_new_block callback fires."""
    from luracoin.network.node import Node
    from luracoin.pow import proof_of_work

    node = Node(port=19999, seed_nodes=[])
    callback_called = []
    node.on_new_block = lambda: callback_called.append(True)

    # Save genesis so handle_block expects height=1
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    genesis = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )
    genesis.save()

    # Create valid block at height 1
    coinbase1 = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(1),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block1 = Block(
        version=1, height=1, miner=WALLET_1["address"],
        prev_block_hash=genesis.id, timestamp=1_623_168_500,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase1],
    )
    proof_of_work(block1)

    accepted = node._handle_block(block1.serialize())
    assert accepted is True
    assert len(callback_called) == 1


def test_node_handle_block_no_callback_on_reject():
    """Callback should NOT fire when block is rejected."""
    from luracoin.network.node import Node

    node = Node(port=19999, seed_nodes=[])
    callback_called = []
    node.on_new_block = lambda: callback_called.append(True)

    # Invalid block data
    accepted = node._handle_block(b"garbage")
    assert accepted is False
    assert len(callback_called) == 0
