import struct
import socket
import pytest
from luracoin.config import Config
from luracoin.helpers import sha256d
from luracoin.network.protocol import (
    HEADER_SIZE,
    CMD_VERSION, CMD_VERACK, CMD_GETPEERS, CMD_PEERS,
    CMD_GETBLOCKS, CMD_BLOCK, CMD_TX, CMD_INV, CMD_GETDATA,
    CMD_PING, CMD_PONG,
    INV_BLOCK, INV_TX,
    _checksum,
    encode_command, decode_command,
    serialize_message, deserialize_header, validate_message,
    build_version_payload, parse_version_payload,
    build_peers_payload, parse_peers_payload,
    build_getblocks_payload, parse_getblocks_payload,
    build_inv_payload, parse_inv_payload,
    build_ping_payload, parse_ping_payload,
)


# ---------------------------------------------------------------------------
# Command encoding
# ---------------------------------------------------------------------------

def test_encode_command_pads_to_12_bytes():
    assert encode_command("version") == CMD_VERSION
    assert len(encode_command("version")) == 12


def test_encode_command_short():
    result = encode_command("tx")
    assert result == CMD_TX
    assert len(result) == 12


def test_encode_command_too_long_raises():
    with pytest.raises(ValueError):
        encode_command("a" * 13)


def test_decode_command_strips_nulls():
    assert decode_command(CMD_VERSION) == "version"
    assert decode_command(CMD_TX) == "tx"
    assert decode_command(CMD_PING) == "ping"


def test_encode_decode_roundtrip():
    for name in ["version", "verack", "getpeers", "peers", "getblocks",
                  "block", "tx", "inv", "getdata", "ping", "pong"]:
        assert decode_command(encode_command(name)) == name


# ---------------------------------------------------------------------------
# All command constants are 12 bytes
# ---------------------------------------------------------------------------

def test_all_commands_are_12_bytes():
    cmds = [CMD_VERSION, CMD_VERACK, CMD_GETPEERS, CMD_PEERS,
            CMD_GETBLOCKS, CMD_BLOCK, CMD_TX, CMD_INV, CMD_GETDATA,
            CMD_PING, CMD_PONG]
    for cmd in cmds:
        assert len(cmd) == 12


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

def test_checksum_is_4_bytes():
    assert len(_checksum(b"hello")) == 4


def test_checksum_matches_sha256d_prefix():
    payload = b"test payload"
    expected = bytes.fromhex(sha256d(payload))[:4]
    assert _checksum(payload) == expected


def test_checksum_empty_payload():
    result = _checksum(b"")
    assert len(result) == 4


def test_checksum_different_payloads_differ():
    assert _checksum(b"aaa") != _checksum(b"bbb")


# ---------------------------------------------------------------------------
# Message serialization / deserialization
# ---------------------------------------------------------------------------

def test_serialize_message_structure():
    msg = serialize_message(CMD_PING, b"\x01\x02\x03\x04")
    assert msg[:4] == Config.MAGIC_BYTES
    assert msg[4:16] == CMD_PING
    length = struct.unpack("<I", msg[16:20])[0]
    assert length == 4
    assert msg[24:] == b"\x01\x02\x03\x04"


def test_serialize_empty_payload():
    msg = serialize_message(CMD_VERACK)
    assert len(msg) == HEADER_SIZE
    length = struct.unpack("<I", msg[16:20])[0]
    assert length == 0


def test_deserialize_header():
    payload = b"testdata"
    msg = serialize_message(CMD_BLOCK, payload)
    header = deserialize_header(msg[:HEADER_SIZE])
    assert header["magic"] == Config.MAGIC_BYTES
    assert header["command"] == CMD_BLOCK
    assert header["payload_length"] == len(payload)
    assert header["checksum"] == _checksum(payload)


def test_deserialize_header_too_short_raises():
    with pytest.raises(ValueError):
        deserialize_header(b"\x00" * 10)


def test_validate_message_good():
    payload = b"hello"
    msg = serialize_message(CMD_TX, payload)
    header = deserialize_header(msg[:HEADER_SIZE])
    assert validate_message(header, payload) is True


def test_validate_message_bad_magic():
    payload = b"hello"
    msg = serialize_message(CMD_TX, payload)
    header = deserialize_header(msg[:HEADER_SIZE])
    header["magic"] = b"\x00\x00\x00\x00"
    assert validate_message(header, payload) is False


def test_validate_message_bad_checksum():
    payload = b"hello"
    msg = serialize_message(CMD_TX, payload)
    header = deserialize_header(msg[:HEADER_SIZE])
    assert validate_message(header, b"tampered") is False


# ---------------------------------------------------------------------------
# Version payload
# ---------------------------------------------------------------------------

def test_version_payload_roundtrip():
    payload = build_version_payload(
        version=1, height=42, timestamp=1_623_168_442, listening_port=9999
    )
    assert len(payload) == 14
    parsed = parse_version_payload(payload)
    assert parsed["version"] == 1
    assert parsed["height"] == 42
    assert parsed["timestamp"] == 1_623_168_442
    assert parsed["listening_port"] == 9999


def test_version_payload_zero_values():
    payload = build_version_payload(0, 0, 0, 0)
    parsed = parse_version_payload(payload)
    assert parsed == {"version": 0, "height": 0, "timestamp": 0, "listening_port": 0}


def test_version_payload_max_values():
    payload = build_version_payload(
        version=0xFFFFFFFF, height=0xFFFFFFFF,
        timestamp=0xFFFFFFFF, listening_port=0xFFFF
    )
    parsed = parse_version_payload(payload)
    assert parsed["version"] == 0xFFFFFFFF
    assert parsed["height"] == 0xFFFFFFFF
    assert parsed["listening_port"] == 0xFFFF


def test_version_full_message_roundtrip():
    payload = build_version_payload(1, 100, 1_623_168_442, 9999)
    msg = serialize_message(CMD_VERSION, payload)
    header = deserialize_header(msg[:HEADER_SIZE])
    assert validate_message(header, payload) is True
    assert decode_command(header["command"]) == "version"
    parsed = parse_version_payload(msg[HEADER_SIZE:])
    assert parsed["height"] == 100


# ---------------------------------------------------------------------------
# Peers payload
# ---------------------------------------------------------------------------

def test_peers_payload_roundtrip():
    peers = [("192.168.1.1", 9999), ("10.0.0.1", 8888)]
    payload = build_peers_payload(peers)
    parsed = parse_peers_payload(payload)
    assert parsed == peers


def test_peers_payload_empty():
    payload = build_peers_payload([])
    parsed = parse_peers_payload(payload)
    assert parsed == []


def test_peers_payload_single():
    peers = [("127.0.0.1", 9999)]
    payload = build_peers_payload(peers)
    assert len(payload) == 2 + 6  # count(2) + 1 * (ip4 + port2)
    parsed = parse_peers_payload(payload)
    assert parsed == peers


def test_peers_payload_size():
    peers = [("1.2.3.4", 1000), ("5.6.7.8", 2000), ("9.10.11.12", 3000)]
    payload = build_peers_payload(peers)
    assert len(payload) == 2 + 3 * 6


# ---------------------------------------------------------------------------
# Getblocks payload
# ---------------------------------------------------------------------------

def test_getblocks_payload_roundtrip():
    payload = build_getblocks_payload(start_height=500, count=50)
    assert len(payload) == 6
    parsed = parse_getblocks_payload(payload)
    assert parsed["start_height"] == 500
    assert parsed["count"] == 50


def test_getblocks_payload_zero():
    payload = build_getblocks_payload(0, 0)
    parsed = parse_getblocks_payload(payload)
    assert parsed == {"start_height": 0, "count": 0}


# ---------------------------------------------------------------------------
# Inv payload
# ---------------------------------------------------------------------------

def test_inv_payload_block_roundtrip():
    hash_bytes = b"\xab" * 32
    payload = build_inv_payload(INV_BLOCK, hash_bytes)
    assert len(payload) == 33
    parsed = parse_inv_payload(payload)
    assert parsed["type"] == INV_BLOCK
    assert parsed["hash"] == hash_bytes


def test_inv_payload_tx_roundtrip():
    hash_bytes = b"\xcd" * 32
    payload = build_inv_payload(INV_TX, hash_bytes)
    parsed = parse_inv_payload(payload)
    assert parsed["type"] == INV_TX
    assert parsed["hash"] == hash_bytes


# ---------------------------------------------------------------------------
# Ping/Pong payload
# ---------------------------------------------------------------------------

def test_ping_payload_roundtrip():
    payload = build_ping_payload(nonce=123456789)
    assert len(payload) == 8
    parsed = parse_ping_payload(payload)
    assert parsed["nonce"] == 123456789


def test_ping_payload_large_nonce():
    nonce = 0xFFFFFFFFFFFFFFFF
    payload = build_ping_payload(nonce)
    parsed = parse_ping_payload(payload)
    assert parsed["nonce"] == nonce


def test_ping_pong_full_message():
    nonce = 42
    ping_payload = build_ping_payload(nonce)
    ping_msg = serialize_message(CMD_PING, ping_payload)

    header = deserialize_header(ping_msg[:HEADER_SIZE])
    assert decode_command(header["command"]) == "ping"
    assert validate_message(header, ping_payload) is True

    # Pong echoes the same nonce
    pong_msg = serialize_message(CMD_PONG, ping_payload)
    pong_header = deserialize_header(pong_msg[:HEADER_SIZE])
    assert decode_command(pong_header["command"]) == "pong"
    pong_parsed = parse_ping_payload(pong_msg[HEADER_SIZE:])
    assert pong_parsed["nonce"] == nonce


# ---------------------------------------------------------------------------
# Inventory type constants
# ---------------------------------------------------------------------------

def test_inv_types_are_distinct():
    assert INV_BLOCK != INV_TX
    assert INV_BLOCK == 0x01
    assert INV_TX == 0x02
