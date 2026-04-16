import asyncio
import struct
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from luracoin.network.peer import PeerConnection
from luracoin.network.protocol import (
    HEADER_SIZE, CMD_VERSION, CMD_VERACK, CMD_PING, CMD_PONG,
    serialize_message, build_version_payload, build_ping_payload,
)


def _make_mock_streams():
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = MagicMock(spec=asyncio.StreamWriter)
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return reader, writer


def _msg_to_reads(msg: bytes):
    """Split a full message into header + payload read calls."""
    header = msg[:HEADER_SIZE]
    payload = msg[HEADER_SIZE:]
    return header, payload


# ---------------------------------------------------------------------------
# Basic properties
# ---------------------------------------------------------------------------

def test_peer_address():
    reader, writer = _make_mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    assert peer.address == ("10.0.0.1", 9999)
    assert peer.connected is True
    assert peer.inbound is False


def test_peer_inbound():
    reader, writer = _make_mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999, inbound=True)
    assert peer.inbound is True


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_writes_full_message():
    reader, writer = _make_mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)

    await peer.send(CMD_PING, build_ping_payload(42))

    writer.write.assert_called_once()
    sent_data = writer.write.call_args[0][0]
    assert sent_data[:4] == b"\xbaw\xd8\x9f"  # magic bytes
    assert sent_data[4:16] == CMD_PING


@pytest.mark.asyncio
async def test_send_empty_payload():
    reader, writer = _make_mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)

    await peer.send(CMD_VERACK)

    sent_data = writer.write.call_args[0][0]
    assert len(sent_data) == HEADER_SIZE


# ---------------------------------------------------------------------------
# receive()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_receive_valid_message():
    reader, writer = _make_mock_streams()
    payload = build_ping_payload(123)
    msg = serialize_message(CMD_PING, payload)
    header_bytes, payload_bytes = _msg_to_reads(msg)

    reader.readexactly = AsyncMock(side_effect=[header_bytes, payload_bytes])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, recv_payload = await peer.receive()

    assert cmd == CMD_PING
    assert recv_payload == payload


@pytest.mark.asyncio
async def test_receive_empty_payload_message():
    reader, writer = _make_mock_streams()
    msg = serialize_message(CMD_VERACK)

    reader.readexactly = AsyncMock(return_value=msg[:HEADER_SIZE])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, recv_payload = await peer.receive()

    assert cmd == CMD_VERACK
    assert recv_payload == b""


@pytest.mark.asyncio
async def test_receive_timeout_returns_none():
    reader, writer = _make_mock_streams()
    reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError)

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, payload = await peer.receive(timeout=0.1)

    assert cmd is None
    assert payload is None


@pytest.mark.asyncio
async def test_receive_incomplete_read_returns_none():
    reader, writer = _make_mock_streams()
    reader.readexactly = AsyncMock(
        side_effect=asyncio.IncompleteReadError(b"", 24)
    )

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, payload = await peer.receive()

    assert cmd is None
    assert payload is None


@pytest.mark.asyncio
async def test_receive_connection_error_returns_none():
    reader, writer = _make_mock_streams()
    reader.readexactly = AsyncMock(side_effect=ConnectionResetError)

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, payload = await peer.receive()

    assert cmd is None


@pytest.mark.asyncio
async def test_receive_invalid_magic_returns_none():
    reader, writer = _make_mock_streams()
    payload = build_ping_payload(1)
    msg = serialize_message(CMD_PING, payload)

    # Corrupt magic bytes
    bad_msg = b"\x00\x00\x00\x00" + msg[4:]
    header_bytes = bad_msg[:HEADER_SIZE]
    payload_bytes = bad_msg[HEADER_SIZE:]

    reader.readexactly = AsyncMock(side_effect=[header_bytes, payload_bytes])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    cmd, recv_payload = await peer.receive()

    assert cmd is None


@pytest.mark.asyncio
async def test_receive_updates_last_seen():
    reader, writer = _make_mock_streams()
    msg = serialize_message(CMD_VERACK)
    reader.readexactly = AsyncMock(return_value=msg[:HEADER_SIZE])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    before = peer.last_seen
    await asyncio.sleep(0.01)
    await peer.receive()

    assert peer.last_seen >= before


# ---------------------------------------------------------------------------
# handshake()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outbound_handshake_success():
    reader, writer = _make_mock_streams()

    remote_version = build_version_payload(1, 50, int(time.time()), 9999)
    version_msg = serialize_message(CMD_VERSION, remote_version)
    verack_msg = serialize_message(CMD_VERACK)

    v_header, v_payload = _msg_to_reads(version_msg)
    va_header = verack_msg[:HEADER_SIZE]

    reader.readexactly = AsyncMock(
        side_effect=[v_header, v_payload, va_header]
    )

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999, inbound=False)
    result = await peer.handshake(local_version=1, local_height=10, local_port=9999)

    assert result is True
    assert peer.version_info["height"] == 50


@pytest.mark.asyncio
async def test_outbound_handshake_no_version_fails():
    reader, writer = _make_mock_streams()

    # Remote sends verack instead of version
    verack_msg = serialize_message(CMD_VERACK)
    reader.readexactly = AsyncMock(return_value=verack_msg[:HEADER_SIZE])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999, inbound=False)
    result = await peer.handshake(local_version=1, local_height=0, local_port=9999)

    assert result is False


@pytest.mark.asyncio
async def test_outbound_handshake_no_verack_fails():
    reader, writer = _make_mock_streams()

    remote_version = build_version_payload(1, 50, int(time.time()), 9999)
    version_msg = serialize_message(CMD_VERSION, remote_version)
    ping_msg = serialize_message(CMD_PING, build_ping_payload(1))

    v_header, v_payload = _msg_to_reads(version_msg)
    p_header, p_payload = _msg_to_reads(ping_msg)

    reader.readexactly = AsyncMock(
        side_effect=[v_header, v_payload, p_header, p_payload]
    )

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999, inbound=False)
    result = await peer.handshake(local_version=1, local_height=0, local_port=9999)

    assert result is False


@pytest.mark.asyncio
async def test_inbound_handshake_success():
    reader, writer = _make_mock_streams()

    remote_version = build_version_payload(1, 100, int(time.time()), 8888)
    version_msg = serialize_message(CMD_VERSION, remote_version)
    verack_msg = serialize_message(CMD_VERACK)

    v_header, v_payload = _msg_to_reads(version_msg)
    va_header = verack_msg[:HEADER_SIZE]

    reader.readexactly = AsyncMock(
        side_effect=[v_header, v_payload, va_header]
    )

    peer = PeerConnection(reader, writer, "10.0.0.1", 8888, inbound=True)
    result = await peer.handshake(local_version=1, local_height=5, local_port=9999)

    assert result is True
    assert peer.version_info["height"] == 100
    assert peer.version_info["listening_port"] == 8888


@pytest.mark.asyncio
async def test_inbound_handshake_no_version_fails():
    reader, writer = _make_mock_streams()
    reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError)

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999, inbound=True)
    result = await peer.handshake(local_version=1, local_height=0, local_port=9999)

    assert result is False


# ---------------------------------------------------------------------------
# send_ping()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_ping_success():
    reader, writer = _make_mock_streams()

    pong_payload = build_ping_payload(42)
    pong_msg = serialize_message(CMD_PONG, pong_payload)
    p_header, p_payload = _msg_to_reads(pong_msg)

    reader.readexactly = AsyncMock(side_effect=[p_header, p_payload])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    result = await peer.send_ping(42)

    assert result is True


@pytest.mark.asyncio
async def test_send_ping_wrong_nonce_fails():
    reader, writer = _make_mock_streams()

    pong_payload = build_ping_payload(999)  # wrong nonce
    pong_msg = serialize_message(CMD_PONG, pong_payload)
    p_header, p_payload = _msg_to_reads(pong_msg)

    reader.readexactly = AsyncMock(side_effect=[p_header, p_payload])

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    result = await peer.send_ping(42)

    assert result is False


@pytest.mark.asyncio
async def test_send_ping_timeout_fails():
    reader, writer = _make_mock_streams()
    reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError)

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    result = await peer.send_ping(42)

    assert result is False


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disconnect():
    reader, writer = _make_mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)

    assert peer.connected is True
    await peer.disconnect()
    assert peer.connected is False
    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_handles_error():
    reader, writer = _make_mock_streams()
    writer.close = MagicMock(side_effect=OSError("broken"))

    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)
    await peer.disconnect()

    assert peer.connected is False
