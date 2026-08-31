"""
Manages a single peer connection over asyncio streams.
"""

import asyncio
import time
from luracoin.config import Config
from luracoin.network.protocol import (
    HEADER_SIZE,
    CMD_VERSION,
    CMD_VERACK,
    CMD_PING,
    CMD_PONG,
    serialize_message,
    deserialize_header,
    validate_message,
    payload_length_is_valid,
    payload_is_valid,
    build_version_payload,
    parse_version_payload,
    build_ping_payload,
    parse_ping_payload,
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
        max_payload_size: int = None,
    ):
        self.reader = reader
        self.writer = writer
        self.host = host
        self.port = port
        self.inbound = inbound
        self.connected = True
        self.version_info = None
        self.last_seen = time.time()
        self.max_payload_size = (
            Config.MAX_P2P_PAYLOAD
            if max_payload_size is None
            else max_payload_size
        )
        self.disconnect_reason = None
        self._send_lock = asyncio.Lock()
        self._receive_lock = asyncio.Lock()
        self._closed = False
        # Set by Node once its single reader/dispatcher owns the stream.
        self._node_managed = False

    @property
    def address(self) -> tuple:
        return (self.host, self.port)

    async def send(self, command: bytes, payload: bytes = b"") -> None:
        """Send a protocol message to this peer."""
        if not self.connected:
            raise ConnectionError("Peer is disconnected")
        if len(payload) > self.max_payload_size:
            raise ValueError("P2P payload exceeds peer maximum")
        if not payload_is_valid(command, payload):
            raise ValueError("Malformed outbound P2P payload")

        msg = serialize_message(command, payload)
        try:
            async with self._send_lock:
                self.writer.write(msg)
                await asyncio.wait_for(
                    self.writer.drain(),
                    timeout=Config.P2P_SEND_TIMEOUT,
                )
        except (asyncio.TimeoutError, ConnectionError, OSError) as exc:
            self.connected = False
            raise ConnectionError("Peer write failed or timed out") from exc

    async def receive(self, timeout: float = 30.0) -> tuple:
        """
        Read one protocol message from this peer.

        Return command/payload bytes, or ``(None, None)`` on error/timeout.
        """
        async with self._receive_lock:
            try:
                header_data = await asyncio.wait_for(
                    self.reader.readexactly(HEADER_SIZE), timeout=timeout
                )
            except (
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
                ConnectionError,
                OSError,
            ):
                return None, None

            try:
                header = deserialize_header(header_data)
            except (ValueError, TypeError):
                self.disconnect_reason = "malformed header"
                return None, None

            payload_length = header["payload_length"]
            if (
                payload_length > self.max_payload_size
                or not payload_length_is_valid(
                    header["command"], payload_length
                )
            ):
                self.disconnect_reason = "invalid payload length"
                return None, None

            payload = b""
            if payload_length > 0:
                try:
                    payload = await asyncio.wait_for(
                        self.reader.readexactly(payload_length),
                        timeout=timeout,
                    )
                except (
                    asyncio.TimeoutError,
                    asyncio.IncompleteReadError,
                    ConnectionError,
                    OSError,
                ):
                    return None, None

            if not validate_message(header, payload):
                self.disconnect_reason = "invalid message framing"
                return None, None
            if not payload_is_valid(header["command"], payload):
                self.disconnect_reason = "malformed payload"
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

        try:
            if not self.inbound:
                # Outbound: we initiate
                await self.send(CMD_VERSION, version_payload)
                cmd, payload = await self.receive()
                if cmd != CMD_VERSION:
                    return False
                self.version_info = parse_version_payload(payload)
                if not self._compatible_version(
                    self.version_info, local_version
                ):
                    return False
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
                if not self._compatible_version(
                    self.version_info, local_version
                ):
                    return False
                await self.send(CMD_VERSION, version_payload)
                await self.send(CMD_VERACK)
                cmd, _ = await self.receive()
                if cmd != CMD_VERACK:
                    return False
        except (ConnectionError, OSError, ValueError):
            return False

        return True

    @staticmethod
    def _compatible_version(version_info: dict, local_version: int) -> bool:
        """Fail the handshake before VERACK for another protocol or chain."""
        return (
            version_info.get("version") == local_version
            and version_info.get("chain_id") == Config.CHAIN_ID
            and 1 <= version_info.get("listening_port", 0) <= 0xFFFF
        )

    async def send_ping(self, nonce: int) -> bool:
        """Send a standalone ping and synchronously wait for its pong.

        Managed Node connections use the node dispatcher instead. This method
        is retained for callers that intentionally own the peer's only reader.
        """
        if self._node_managed:
            raise RuntimeError("Node-managed peers must use Node.ping_peers")
        await self.send(CMD_PING, build_ping_payload(nonce))
        cmd, payload = await self.receive(timeout=10.0)
        if cmd != CMD_PONG:
            return False
        pong_data = parse_ping_payload(payload)
        return pong_data["nonce"] == nonce

    async def disconnect(self) -> None:
        """Close the connection."""
        self.connected = False
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
