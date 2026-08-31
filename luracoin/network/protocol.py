"""
Luracoin P2P binary protocol.

Message format:
    magic(4B) + command(12B) + payload_length(4B) + checksum(4B)
    followed by the payload

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
BLOCK_HEADER_SIZE = 118
MAX_PEER_ADDRESSES = 256
# Version 2 adds the chain id to VERSION. It is deliberately incompatible
# with the original 14-byte v1 handshake.
PROTOCOL_VERSION = 2

# Inventory types
INV_BLOCK = 0x01
INV_TX = 0x02

KNOWN_COMMANDS = {
    CMD_VERSION,
    CMD_VERACK,
    CMD_GETPEERS,
    CMD_PEERS,
    CMD_GETBLOCKS,
    CMD_BLOCK,
    CMD_TX,
    CMD_INV,
    CMD_GETDATA,
    CMD_PING,
    CMD_PONG,
}


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
    if command not in KNOWN_COMMANDS:
        raise ValueError("Unknown P2P command")
    if len(payload) > Config.MAX_P2P_PAYLOAD:
        raise ValueError("P2P payload exceeds configured maximum")

    length = struct.pack("<I", len(payload))
    checksum = _checksum(payload)
    return Config.MAGIC_BYTES + command + length + checksum + payload


def deserialize_header(data: bytes) -> dict:
    """
    Parse a 24-byte message header.

    Returns dict with: magic, command, payload_length, checksum
    """
    if len(data) != HEADER_SIZE:
        raise ValueError(f"Header must be exactly {HEADER_SIZE} bytes")

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
    """Validate transport framing, magic bytes, length, and checksum."""
    if header["magic"] != Config.MAGIC_BYTES:
        return False
    if header["command"] not in KNOWN_COMMANDS:
        return False
    if header["payload_length"] != len(payload):
        return False
    if header["checksum"] != _checksum(payload):
        return False
    return True


def payload_length_is_valid(command: bytes, payload_length: int) -> bool:
    """Return whether a payload length is valid before allocating it.

    The global maximum protects the stream reader from attacker-controlled
    multi-gigabyte allocations. Fixed-size commands are rejected before their
    payload is read, and block framing must align to whole transactions.
    """
    if command not in KNOWN_COMMANDS:
        return False
    if payload_length < 0 or payload_length > Config.MAX_P2P_PAYLOAD:
        return False

    exact_lengths = {
        CMD_VERSION: 18,
        CMD_VERACK: 0,
        CMD_GETPEERS: 0,
        CMD_GETBLOCKS: 6,
        CMD_TX: Config.TRANSACTION_LENGTH,
        CMD_INV: 33,
        CMD_GETDATA: 33,
        CMD_PING: 8,
        CMD_PONG: 8,
    }
    expected = exact_lengths.get(command)
    if expected is not None:
        return payload_length == expected
    if command == CMD_PEERS:
        return 2 <= payload_length <= 2 + (MAX_PEER_ADDRESSES * 6)
    if command == CMD_BLOCK:
        return (
            payload_length >= BLOCK_HEADER_SIZE
            and payload_length <= Config.MAX_BLOCK_SERIALIZED_SIZE
            and (payload_length - BLOCK_HEADER_SIZE)
            % Config.TRANSACTION_LENGTH
            == 0
        )
    return False


def payload_is_valid(command: bytes, payload: bytes) -> bool:
    """Validate the structural shape of a command payload."""
    if not payload_length_is_valid(command, len(payload)):
        return False
    try:
        if command == CMD_VERSION:
            parse_version_payload(payload)
        elif command == CMD_PEERS:
            parse_peers_payload(payload)
        elif command == CMD_GETBLOCKS:
            parse_getblocks_payload(payload)
        elif command in (CMD_INV, CMD_GETDATA):
            parse_inv_payload(payload)
        elif command in (CMD_PING, CMD_PONG):
            parse_ping_payload(payload)
    except (ValueError, struct.error, OSError):
        return False
    return True


# ---------------------------------------------------------------------------
# Payload builders / parsers for each command
# ---------------------------------------------------------------------------


def build_version_payload(
    version: int,
    height: int,
    timestamp: int,
    listening_port: int,
    chain_id: int = None,
) -> bytes:
    """Build the network compatibility handshake (18 bytes).

    protocol_version(4B) + chain_id(4B) + height(4B) + timestamp(4B) +
    listening_port(2B). ``chain_id`` defaults to the active network so old
    Python call sites with four arguments continue to build valid messages.
    """
    if chain_id is None:
        chain_id = Config.CHAIN_ID
    return struct.pack(
        "<IIIIH", version, chain_id, height, timestamp, listening_port
    )


def parse_version_payload(payload: bytes) -> dict:
    if len(payload) != 18:
        raise ValueError("VERSION payload must be exactly 18 bytes")
    version, chain_id, height, timestamp, port = struct.unpack(
        "<IIIIH", payload
    )
    return {
        "version": version,
        "chain_id": chain_id,
        "height": height,
        "timestamp": timestamp,
        "listening_port": port,
    }


def build_peers_payload(peers: list) -> bytes:
    """
    count(2B) + [ip(4B) + port(2B)] * N

    peers: list of (ip_str, port_int) tuples
    """
    if len(peers) > MAX_PEER_ADDRESSES:
        raise ValueError("Too many peer addresses")
    data = struct.pack("<H", len(peers))
    for ip_str, port in peers:
        if not 1 <= port <= 0xFFFF:
            raise ValueError(f"Invalid peer port: {port}")
        try:
            ip_bytes = socket.inet_pton(socket.AF_INET, ip_str)
        except OSError as exc:
            raise ValueError(f"Invalid IPv4 peer address: {ip_str}") from exc
        data += ip_bytes + struct.pack("<H", port)
    return data


def parse_peers_payload(payload: bytes) -> list:
    """Returns list of (ip_str, port) tuples."""
    if len(payload) < 2:
        raise ValueError("PEERS payload is too short")
    count = struct.unpack("<H", payload[0:2])[0]
    if count > MAX_PEER_ADDRESSES:
        raise ValueError("PEERS payload advertises too many addresses")
    expected_length = 2 + (count * 6)
    if len(payload) != expected_length:
        raise ValueError("PEERS payload length does not match its count")
    peers = []
    offset = 2
    for _ in range(count):
        ip_bytes = payload[offset : offset + 4]
        port = struct.unpack("<H", payload[offset + 4 : offset + 6])[0]
        if port == 0:
            raise ValueError("Peer port must be non-zero")
        ip_str = socket.inet_ntoa(ip_bytes)
        peers.append((ip_str, port))
        offset += 6
    return peers


def build_getblocks_payload(start_height: int, count: int) -> bytes:
    """start_height(4B) + count(2B)"""
    return struct.pack("<IH", start_height, count)


def parse_getblocks_payload(payload: bytes) -> dict:
    if len(payload) != 6:
        raise ValueError("GETBLOCKS payload must be exactly 6 bytes")
    start_height, count = struct.unpack("<IH", payload)
    return {"start_height": start_height, "count": count}


def build_inv_payload(inv_type: int, hash_bytes: bytes) -> bytes:
    """type(1B) + hash(32B)"""
    if inv_type not in (INV_BLOCK, INV_TX):
        raise ValueError(f"Unsupported inventory type: {inv_type}")
    if len(hash_bytes) != 32:
        raise ValueError("Inventory hashes must be exactly 32 bytes")
    return struct.pack("<B", inv_type) + hash_bytes


def parse_inv_payload(payload: bytes) -> dict:
    if len(payload) != 33:
        raise ValueError("Inventory payload must be exactly 33 bytes")
    inv_type = struct.unpack("<B", payload[0:1])[0]
    if inv_type not in (INV_BLOCK, INV_TX):
        raise ValueError(f"Unsupported inventory type: {inv_type}")
    hash_bytes = payload[1:33]
    return {"type": inv_type, "hash": hash_bytes}


def build_ping_payload(nonce: int) -> bytes:
    """nonce(8B)"""
    return struct.pack("<Q", nonce)


def parse_ping_payload(payload: bytes) -> dict:
    if len(payload) != 8:
        raise ValueError("PING/PONG payload must be exactly 8 bytes")
    nonce = struct.unpack("<Q", payload)[0]
    return {"nonce": nonce}
