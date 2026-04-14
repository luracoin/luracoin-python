"""
Main P2P node: server + peer management + message dispatch.
"""

import asyncio
import time
import logging
import binascii

from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.network.protocol import (
    CMD_VERSION, CMD_VERACK, CMD_GETPEERS, CMD_PEERS,
    CMD_GETBLOCKS, CMD_BLOCK, CMD_TX, CMD_INV, CMD_GETDATA,
    CMD_PING, CMD_PONG,
    INV_BLOCK, INV_TX,
    build_ping_payload, parse_ping_payload,
    parse_getblocks_payload, parse_inv_payload,
    build_inv_payload,
)
from luracoin.network.peer import PeerConnection
from luracoin.network.discovery import PeerDiscovery
from luracoin.network.sync import BlockSync

log = logging.getLogger(__name__)


class Node:
    """
    Luracoin P2P node.

    Listens for incoming connections and connects to known peers.
    Handles message dispatch, block/tx propagation, and sync.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = None,
        seed_nodes: list = None,
        max_peers: int = 8,
        ping_interval: int = 60,
    ):
        self.host = host
        self.port = port or Config.PORT
        self.chain = Chain()
        self.block_sync = BlockSync(self.chain, Block)
        self.discovery = PeerDiscovery(
            seed_nodes=seed_nodes or Config.SEED_NODES,
            max_peers=max_peers,
            local_port=self.port,
        )
        self.peers: dict = {}  # (host, port) -> PeerConnection
        self.max_peers = max_peers
        self.ping_interval = ping_interval
        self.running = False
        self._server = None
        self.known_invs: set = set()  # Set of seen inv hashes to avoid re-broadcast

    @property
    def connected_addresses(self) -> set:
        return set(self.peers.keys())

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start listening and connect to seed nodes."""
        self._server = await asyncio.start_server(
            self._handle_inbound, self.host, self.port
        )
        self.running = True
        log.info(f"Node listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully stop the node."""
        self.running = False
        for addr in list(self.peers.keys()):
            await self.peers[addr].disconnect()
        self.peers.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_inbound(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new inbound connection."""
        peername = writer.get_extra_info("peername")
        host, port = peername[0], peername[1]
        log.info(f"Inbound connection from {host}:{port}")

        peer = PeerConnection(reader, writer, host, port, inbound=True)
        ok = await peer.handshake(
            local_version=1,
            local_height=self.chain.tip,
            local_port=self.port,
        )
        if not ok:
            await peer.disconnect()
            return

        listening_port = peer.version_info["listening_port"]
        addr = (host, listening_port)
        self.peers[addr] = peer
        self.discovery.add_peer(host, listening_port)

        await self._post_handshake(peer)

    async def connect_to_peer(self, host: str, port: int) -> bool:
        """Initiate an outbound connection to a peer."""
        if (host, port) in self.peers:
            return False
        if len(self.peers) >= self.max_peers:
            return False

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
        except (OSError, asyncio.TimeoutError):
            self.discovery.remove_peer(host, port)
            return False

        peer = PeerConnection(reader, writer, host, port, inbound=False)
        ok = await peer.handshake(
            local_version=1,
            local_height=self.chain.tip,
            local_port=self.port,
        )
        if not ok:
            await peer.disconnect()
            return False

        self.peers[(host, port)] = peer
        self.discovery.add_peer(host, port)

        await self._post_handshake(peer)
        return True

    async def _post_handshake(self, peer: PeerConnection) -> None:
        """Actions after a successful handshake: peer exchange + sync."""
        # Request peers
        await peer.send(CMD_GETPEERS)

        # Start sync if they're ahead
        if self.block_sync.needs_sync(peer.version_info["height"]):
            await self._sync_from_peer(peer)

    async def connect_to_seeds(self) -> None:
        """Connect to all known peers we're not yet connected to."""
        to_connect = self.discovery.get_peers_to_connect(self.connected_addresses)
        for host, port in to_connect:
            if len(self.peers) >= self.max_peers:
                break
            await self.connect_to_peer(host, port)

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def handle_message(
        self, peer: PeerConnection, command: bytes, payload: bytes
    ) -> None:
        """Dispatch a received message to the appropriate handler."""
        if command == CMD_GETPEERS:
            response = self.discovery.build_peers_response()
            await peer.send(CMD_PEERS, response)

        elif command == CMD_PEERS:
            self.discovery.handle_peers_message(payload)

        elif command == CMD_GETBLOCKS:
            await self._handle_getblocks(peer, payload)

        elif command == CMD_BLOCK:
            self._handle_block(payload)

        elif command == CMD_TX:
            self._handle_tx(payload)

        elif command == CMD_INV:
            await self._handle_inv(peer, payload)

        elif command == CMD_GETDATA:
            await self._handle_getdata(peer, payload)

        elif command == CMD_PING:
            ping_data = parse_ping_payload(payload)
            await peer.send(CMD_PONG, build_ping_payload(ping_data["nonce"]))

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_getblocks(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        """Send requested blocks to peer."""
        data = parse_getblocks_payload(payload)
        start = data["start_height"]
        count = min(data["count"], 50)

        for height in range(start, start + count):
            block = Block.get(height)
            if block is None:
                break
            await peer.send(CMD_BLOCK, block.serialize())

    def _handle_block(self, payload: bytes) -> bool:
        """Process a received block."""
        return self.block_sync.handle_block(payload)

    def _handle_tx(self, payload: bytes) -> bool:
        """Process a received transaction."""
        try:
            tx = Transaction()
            tx.deserialize(payload)
            return tx.to_transaction_pool()
        except Exception:
            return False

    async def _handle_inv(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        """Handle an inventory announcement."""
        inv_data = parse_inv_payload(payload)
        inv_hash = inv_data["hash"]

        if inv_hash in self.known_invs:
            return

        self.known_invs.add(inv_hash)

        # Request the data
        await peer.send(
            CMD_GETDATA,
            build_inv_payload(inv_data["type"], inv_hash),
        )

    async def _handle_getdata(
        self, peer: PeerConnection, payload: bytes
    ) -> None:
        """Handle a data request."""
        inv_data = parse_inv_payload(payload)

        if inv_data["type"] == INV_BLOCK:
            block_id_hex = inv_data["hash"].hex()
            # Search for block by iterating (simple approach)
            for height in range(self.chain.tip + 1):
                block = Block.get(height)
                if block and block.id == block_id_hex:
                    await peer.send(CMD_BLOCK, block.serialize())
                    return

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def _sync_from_peer(self, peer: PeerConnection) -> None:
        """Download blocks from peer until caught up."""
        self.block_sync.syncing = True

        while self.block_sync.needs_sync(peer.version_info["height"]):
            getblocks_payload = self.block_sync.build_getblocks_request()
            await peer.send(CMD_GETBLOCKS, getblocks_payload)

            # Receive blocks
            blocks_received = 0
            data = parse_getblocks_payload(getblocks_payload)
            expected_count = min(
                data["count"],
                peer.version_info["height"] - self.chain.tip,
            )

            for _ in range(expected_count):
                cmd, block_payload = await peer.receive(timeout=30.0)
                if cmd != CMD_BLOCK or block_payload is None:
                    break
                if self.block_sync.handle_block(block_payload):
                    blocks_received += 1
                else:
                    break

            if blocks_received == 0:
                break

        self.block_sync.syncing = False

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast_block(self, block: Block) -> None:
        """Announce a new block to all peers via INV."""
        inv_payload = self.block_sync.build_block_inv(block.id)
        hash_bytes = binascii.unhexlify(block.id)
        self.known_invs.add(hash_bytes)

        for peer in list(self.peers.values()):
            try:
                await peer.send(CMD_INV, inv_payload)
            except Exception:
                pass

    async def broadcast_tx(self, tx: Transaction) -> None:
        """Send a transaction to all peers."""
        tx_payload = tx.serialize()
        for peer in list(self.peers.values()):
            try:
                await peer.send(CMD_TX, tx_payload)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Peer message loop
    # ------------------------------------------------------------------

    async def listen_to_peer(self, peer: PeerConnection) -> None:
        """Continuously read messages from a peer."""
        while self.running and peer.connected:
            cmd, payload = await peer.receive(timeout=self.ping_interval * 2)
            if cmd is None:
                break
            await self.handle_message(peer, cmd, payload)

        addr = peer.address
        if addr in self.peers:
            del self.peers[addr]
        await peer.disconnect()

    # ------------------------------------------------------------------
    # Keep-alive
    # ------------------------------------------------------------------

    async def ping_peers(self) -> None:
        """Send pings to all peers, disconnect dead ones."""
        nonce = int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF
        for addr, peer in list(self.peers.items()):
            ok = await peer.send_ping(nonce)
            if not ok:
                log.info(f"Peer {addr} failed ping, disconnecting")
                del self.peers[addr]
                await peer.disconnect()
