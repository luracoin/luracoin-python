"""
Manages a single peer connection over asyncio streams.
"""

import asyncio
import time
from luracoin.network.protocol import (
    HEADER_SIZE,
    CMD_VERSION, CMD_VERACK, CMD_PING, CMD_PONG,
    serialize_message, deserialize_header, validate_message,
    build_version_payload, parse_version_payload,
    build_ping_payload, parse_ping_payload,
)


class PeerConnection:
    """A single TCP connection to a remote peer."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        host: str,
        port: int,
        inbound: bool = False,
    ):
        self.reader = reader
        self.writer = writer
        self.host = host
        self.port = port
        self.inbound = inbound
        self.connected = True
        self.version_info = None
        self.last_seen = time.time()

    @property
    def address(self) -> tuple:
        return (self.host, self.port)

    async def send(self, command: bytes, payload: bytes = b"") -> None:
        """Send a protocol message to this peer."""
        msg = serialize_message(command, payload)
        self.writer.write(msg)
        await self.writer.drain()

    async def receive(self, timeout: float = 30.0) -> tuple:
        """
        Read one protocol message from this peer.

        Returns: (command_bytes, payload_bytes) or (None, None) on error/timeout.
        """
        try:
            header_data = await asyncio.wait_for(
                self.reader.readexactly(HEADER_SIZE), timeout=timeout
            )
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            return None, None

        header = deserialize_header(header_data)
        payload = b""
        if header["payload_length"] > 0:
            try:
                payload = await asyncio.wait_for(
                    self.reader.readexactly(header["payload_length"]),
                    timeout=timeout,
                )
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
                return None, None

        if not validate_message(header, payload):
            return None, None

        self.last_seen = time.time()
        return header["command"], payload

    async def handshake(
        self, local_version: int, local_height: int, local_port: int
    ) -> bool:
        """
        Perform the version/verack handshake.

        Outbound: send VERSION, receive VERSION, send VERACK, receive VERACK.
        Inbound: receive VERSION, send VERSION, receive VERACK, send VERACK.

        Returns True if handshake succeeded.
        """
        version_payload = build_version_payload(
            version=local_version,
            height=local_height,
            timestamp=int(time.time()),
            listening_port=local_port,
        )

        if not self.inbound:
            # Outbound: we initiate
            await self.send(CMD_VERSION, version_payload)
            cmd, payload = await self.receive()
            if cmd != CMD_VERSION:
                return False
            self.version_info = parse_version_payload(payload)
            await self.send(CMD_VERACK)
            cmd, _ = await self.receive()
            if cmd != CMD_VERACK:
                return False
        else:
            # Inbound: they initiate
            cmd, payload = await self.receive()
            if cmd != CMD_VERSION:
                return False
            self.version_info = parse_version_payload(payload)
            await self.send(CMD_VERSION, version_payload)
            await self.send(CMD_VERACK)
            cmd, _ = await self.receive()
            if cmd != CMD_VERACK:
                return False

        return True

    async def send_ping(self, nonce: int) -> bool:
        """Send ping and wait for matching pong. Returns True on success."""
        await self.send(CMD_PING, build_ping_payload(nonce))
        cmd, payload = await self.receive(timeout=10.0)
        if cmd != CMD_PONG:
            return False
        pong_data = parse_ping_payload(payload)
        return pong_data["nonce"] == nonce

    async def disconnect(self) -> None:
        """Close the connection."""
        self.connected = False
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
