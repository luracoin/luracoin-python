"""
Luracoin P2P binary protocol.

Message format:
    magic_bytes (4B) + command (12B padded \\x00) + payload_length (4B) + checksum (4B) + payload

Checksum: first 4 bytes of sha256d(payload).
"""

import struct
import socket
from luracoin.config import Config
from luracoin.helpers import sha256d


# Command constants (12 bytes each, right-padded with \x00)
CMD_VERSION = b"version\x00\x00\x00\x00\x00"
CMD_VERACK = b"verack\x00\x00\x00\x00\x00\x00"
CMD_GETPEERS = b"getpeers\x00\x00\x00\x00"
CMD_PEERS = b"peers\x00\x00\x00\x00\x00\x00\x00"
CMD_GETBLOCKS = b"getblocks\x00\x00\x00"
CMD_BLOCK = b"block\x00\x00\x00\x00\x00\x00\x00"
CMD_TX = b"tx\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
CMD_INV = b"inv\x00\x00\x00\x00\x00\x00\x00\x00\x00"
CMD_GETDATA = b"getdata\x00\x00\x00\x00\x00"
CMD_PING = b"ping\x00\x00\x00\x00\x00\x00\x00\x00"
CMD_PONG = b"pong\x00\x00\x00\x00\x00\x00\x00\x00"

HEADER_SIZE = 24  # 4 + 12 + 4 + 4

# Inventory types
INV_BLOCK = 0x01
INV_TX = 0x02


def _checksum(payload: bytes) -> bytes:
    """First 4 bytes of sha256d(payload)."""
    return bytes.fromhex(sha256d(payload))[:4]


def encode_command(name: str) -> bytes:
    """Encode a command string to 12 bytes, right-padded with \\x00."""
    encoded = name.encode("ascii")
    if len(encoded) > 12:
        raise ValueError(f"Command name too long: {name}")
    return encoded.ljust(12, b"\x00")


def decode_command(raw: bytes) -> str:
    """Decode a 12-byte command field to a string."""
    return raw.rstrip(b"\x00").decode("ascii")


def serialize_message(command: bytes, payload: bytes = b"") -> bytes:
    """
    Build a full protocol message.

    Returns: magic(4) + command(12) + length(4) + checksum(4) + payload
    """
    length = struct.pack("<I", len(payload))
    checksum = _checksum(payload)
    return Config.MAGIC_BYTES + command + length + checksum + payload


def deserialize_header(data: bytes) -> dict:
    """
    Parse a 24-byte message header.

    Returns dict with: magic, command, payload_length, checksum
    """
    if len(data) < HEADER_SIZE:
        raise ValueError(f"Header too short: {len(data)} bytes")

    magic = data[0:4]
    command = data[4:16]
    payload_length = struct.unpack("<I", data[16:20])[0]
    checksum = data[20:24]

    return {
        "magic": magic,
        "command": command,
        "payload_length": payload_length,
        "checksum": checksum,
    }


def validate_message(header: dict, payload: bytes) -> bool:
    """Validate magic bytes and checksum."""
    if header["magic"] != Config.MAGIC_BYTES:
        return False
    if header["checksum"] != _checksum(payload):
        return False
    return True


# ---------------------------------------------------------------------------
# Payload builders / parsers for each command
# ---------------------------------------------------------------------------

def build_version_payload(
    version: int, height: int, timestamp: int, listening_port: int
) -> bytes:
    """version(4B) + height(4B) + timestamp(4B) + listening_port(2B) = 14 bytes"""
    return struct.pack("<IIIH", version, height, timestamp, listening_port)


def parse_version_payload(payload: bytes) -> dict:
    version, height, timestamp, port = struct.unpack("<IIIH", payload[:14])
    return {
        "version": version,
        "height": height,
        "timestamp": timestamp,
        "listening_port": port,
    }


def build_peers_payload(peers: list) -> bytes:
    """
    count(2B) + [ip(4B) + port(2B)] * N

    peers: list of (ip_str, port_int) tuples
    """
    data = struct.pack("<H", len(peers))
    for ip_str, port in peers:
        ip_bytes = socket.inet_aton(ip_str)
        data += ip_bytes + struct.pack("<H", port)
    return data


def parse_peers_payload(payload: bytes) -> list:
    """Returns list of (ip_str, port) tuples."""
    count = struct.unpack("<H", payload[0:2])[0]
    peers = []
    offset = 2
    for _ in range(count):
        ip_bytes = payload[offset : offset + 4]
        port = struct.unpack("<H", payload[offset + 4 : offset + 6])[0]
        ip_str = socket.inet_ntoa(ip_bytes)
        peers.append((ip_str, port))
        offset += 6
    return peers


def build_getblocks_payload(start_height: int, count: int) -> bytes:
    """start_height(4B) + count(2B)"""
    return struct.pack("<IH", start_height, count)


def parse_getblocks_payload(payload: bytes) -> dict:
    start_height, count = struct.unpack("<IH", payload[:6])
    return {"start_height": start_height, "count": count}


def build_inv_payload(inv_type: int, hash_bytes: bytes) -> bytes:
    """type(1B) + hash(32B)"""
    return struct.pack("<B", inv_type) + hash_bytes


def parse_inv_payload(payload: bytes) -> dict:
    inv_type = struct.unpack("<B", payload[0:1])[0]
    hash_bytes = payload[1:33]
    return {"type": inv_type, "hash": hash_bytes}


def build_ping_payload(nonce: int) -> bytes:
    """nonce(8B)"""
    return struct.pack("<Q", nonce)


def parse_ping_payload(payload: bytes) -> dict:
    nonce = struct.unpack("<Q", payload[:8])[0]
    return {"nonce": nonce}
