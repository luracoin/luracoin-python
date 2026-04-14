import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from luracoin.network.node import Node
from luracoin.network.peer import PeerConnection
from luracoin.network.protocol import (
    HEADER_SIZE, CMD_VERSION, CMD_VERACK, CMD_GETPEERS, CMD_PEERS,
    CMD_GETBLOCKS, CMD_BLOCK, CMD_TX, CMD_INV, CMD_GETDATA,
    CMD_PING, CMD_PONG, INV_BLOCK, INV_TX,
    serialize_message, build_version_payload, build_peers_payload,
    build_getblocks_payload, build_ping_payload, build_inv_payload,
    parse_ping_payload,
)
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.helpers import mining_reward
from tests.constants import WALLET_1


def _make_mock_peer(host="10.0.0.1", port=9999, height=0):
    peer = MagicMock(spec=PeerConnection)
    peer.host = host
    peer.port = port
    peer.address = (host, port)
    peer.connected = True
    peer.version_info = {"version": 1, "height": height, "timestamp": 0, "listening_port": port}
    peer.send = AsyncMock()
    peer.receive = AsyncMock(return_value=(None, None))
    peer.disconnect = AsyncMock()
    peer.send_ping = AsyncMock(return_value=True)
    return peer


# ---------------------------------------------------------------------------
# Node creation
# ---------------------------------------------------------------------------

def test_node_creation():
    node = Node(port=19999, seed_nodes=[("10.0.0.1", 19999)])
    assert node.port == 19999
    assert node.running is False
    assert len(node.peers) == 0


def test_node_connected_addresses_empty():
    node = Node(port=19999, seed_nodes=[])
    assert node.connected_addresses == set()


def test_node_connected_addresses_with_peers():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer("10.0.0.1", 9999)
    node.peers[("10.0.0.1", 9999)] = peer
    assert ("10.0.0.1", 9999) in node.connected_addresses


# ---------------------------------------------------------------------------
# handle_message: GETPEERS / PEERS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_getpeers_sends_peers_response():
    node = Node(port=19999, seed_nodes=[("10.0.0.2", 9999)])
    peer = _make_mock_peer()

    await node.handle_message(peer, CMD_GETPEERS, b"")

    peer.send.assert_called_once()
    call_args = peer.send.call_args
    assert call_args[0][0] == CMD_PEERS


@pytest.mark.asyncio
async def test_handle_peers_adds_to_discovery():
    node = Node(port=19999, seed_nodes=[], max_peers=10)
    peer = _make_mock_peer()

    payload = build_peers_payload([("10.0.0.5", 8888), ("10.0.0.6", 7777)])
    await node.handle_message(peer, CMD_PEERS, payload)

    assert ("10.0.0.5", 8888) in node.discovery.known_peers
    assert ("10.0.0.6", 7777) in node.discovery.known_peers


# ---------------------------------------------------------------------------
# handle_message: PING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_ping_sends_pong():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    ping_payload = build_ping_payload(42)
    await node.handle_message(peer, CMD_PING, ping_payload)

    peer.send.assert_called_once()
    call_cmd = peer.send.call_args[0][0]
    call_payload = peer.send.call_args[0][1]
    assert call_cmd == CMD_PONG
    assert parse_ping_payload(call_payload)["nonce"] == 42


# ---------------------------------------------------------------------------
# handle_message: GETBLOCKS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_getblocks_sends_blocks():
    node = Node(port=19999, seed_nodes=[])

    # Save a block
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )
    block.save()

    peer = _make_mock_peer()
    payload = build_getblocks_payload(start_height=0, count=10)
    await node.handle_message(peer, CMD_GETBLOCKS, payload)

    peer.send.assert_called_once()
    assert peer.send.call_args[0][0] == CMD_BLOCK


@pytest.mark.asyncio
async def test_handle_getblocks_no_blocks_sends_nothing():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    payload = build_getblocks_payload(start_height=100, count=10)
    await node.handle_message(peer, CMD_GETBLOCKS, payload)

    peer.send.assert_not_called()


# ---------------------------------------------------------------------------
# handle_message: TX
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_tx_invalid_data():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    # Invalid tx data should not crash
    await node.handle_message(peer, CMD_TX, b"garbage")


# ---------------------------------------------------------------------------
# handle_message: INV
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_inv_requests_unknown_data():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    hash_bytes = b"\xab" * 32
    inv_payload = build_inv_payload(INV_BLOCK, hash_bytes)
    await node.handle_message(peer, CMD_INV, inv_payload)

    # Should request the block
    peer.send.assert_called_once()
    assert peer.send.call_args[0][0] == CMD_GETDATA


@pytest.mark.asyncio
async def test_handle_inv_ignores_known():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    hash_bytes = b"\xab" * 32
    node.known_invs.add(hash_bytes)

    inv_payload = build_inv_payload(INV_BLOCK, hash_bytes)
    await node.handle_message(peer, CMD_INV, inv_payload)

    peer.send.assert_not_called()


# ---------------------------------------------------------------------------
# handle_message: GETDATA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_getdata_sends_block():
    node = Node(port=19999, seed_nodes=[])

    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=mining_reward(0),
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )
    block.save()

    peer = _make_mock_peer()
    import binascii
    hash_bytes = binascii.unhexlify(block.id)
    getdata_payload = build_inv_payload(INV_BLOCK, hash_bytes)
    await node.handle_message(peer, CMD_GETDATA, getdata_payload)

    peer.send.assert_called_once()
    assert peer.send.call_args[0][0] == CMD_BLOCK


@pytest.mark.asyncio
async def test_handle_getdata_unknown_block():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer()

    hash_bytes = b"\xff" * 32
    getdata_payload = build_inv_payload(INV_BLOCK, hash_bytes)
    await node.handle_message(peer, CMD_GETDATA, getdata_payload)

    peer.send.assert_not_called()


# ---------------------------------------------------------------------------
# broadcast_block
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_block_sends_inv_to_all_peers():
    node = Node(port=19999, seed_nodes=[])
    peer1 = _make_mock_peer("10.0.0.1", 9999)
    peer2 = _make_mock_peer("10.0.0.2", 9999)
    node.peers[("10.0.0.1", 9999)] = peer1
    node.peers[("10.0.0.2", 9999)] = peer2

    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )

    await node.broadcast_block(block)

    peer1.send.assert_called_once()
    peer2.send.assert_called_once()
    assert peer1.send.call_args[0][0] == CMD_INV
    assert peer2.send.call_args[0][0] == CMD_INV


@pytest.mark.asyncio
async def test_broadcast_block_adds_to_known_invs():
    node = Node(port=19999, seed_nodes=[])
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    block = Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=b"\x1f\x00\xff\xff", nonce=0, txns=[coinbase],
    )

    await node.broadcast_block(block)

    import binascii
    assert binascii.unhexlify(block.id) in node.known_invs


# ---------------------------------------------------------------------------
# broadcast_tx
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_tx_sends_to_all_peers():
    node = Node(port=19999, seed_nodes=[])
    peer1 = _make_mock_peer("10.0.0.1", 9999)
    peer2 = _make_mock_peer("10.0.0.2", 9999)
    node.peers[("10.0.0.1", 9999)] = peer1
    node.peers[("10.0.0.2", 9999)] = peer2

    tx = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    await node.broadcast_tx(tx)

    peer1.send.assert_called_once()
    peer2.send.assert_called_once()
    assert peer1.send.call_args[0][0] == CMD_TX


# ---------------------------------------------------------------------------
# connect_to_peer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_to_peer_already_connected():
    node = Node(port=19999, seed_nodes=[])
    peer = _make_mock_peer("10.0.0.1", 9999)
    node.peers[("10.0.0.1", 9999)] = peer

    result = await node.connect_to_peer("10.0.0.1", 9999)
    assert result is False


@pytest.mark.asyncio
async def test_connect_to_peer_max_peers():
    node = Node(port=19999, seed_nodes=[], max_peers=1)
    node.peers[("10.0.0.1", 9999)] = _make_mock_peer()

    result = await node.connect_to_peer("10.0.0.2", 9999)
    assert result is False


@pytest.mark.asyncio
async def test_connect_to_peer_connection_refused():
    node = Node(port=19999, seed_nodes=[])

    with patch("luracoin.network.node.asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
        mock_conn.side_effect = OSError("Connection refused")
        result = await node.connect_to_peer("10.0.0.1", 9999)

    assert result is False


# ---------------------------------------------------------------------------
# ping_peers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping_peers_removes_dead():
    node = Node(port=19999, seed_nodes=[])
    dead_peer = _make_mock_peer("10.0.0.1", 9999)
    dead_peer.send_ping = AsyncMock(return_value=False)
    node.peers[("10.0.0.1", 9999)] = dead_peer

    alive_peer = _make_mock_peer("10.0.0.2", 9999)
    alive_peer.send_ping = AsyncMock(return_value=True)
    node.peers[("10.0.0.2", 9999)] = alive_peer

    await node.ping_peers()

    assert ("10.0.0.1", 9999) not in node.peers
    assert ("10.0.0.2", 9999) in node.peers
    dead_peer.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_disconnects_all_peers():
    node = Node(port=19999, seed_nodes=[])
    peer1 = _make_mock_peer("10.0.0.1", 9999)
    peer2 = _make_mock_peer("10.0.0.2", 9999)
    node.peers[("10.0.0.1", 9999)] = peer1
    node.peers[("10.0.0.2", 9999)] = peer2

    await node.stop()

    assert node.running is False
    assert len(node.peers) == 0
    peer1.disconnect.assert_called_once()
    peer2.disconnect.assert_called_once()
