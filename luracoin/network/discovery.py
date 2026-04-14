"""
Peer discovery: seed nodes + peer exchange.
"""

from luracoin.network.protocol import (
    CMD_GETPEERS, CMD_PEERS,
    build_peers_payload, parse_peers_payload,
)


class PeerDiscovery:
    """Tracks known peers and manages peer exchange."""

    def __init__(self, seed_nodes: list, max_peers: int = 8, local_port: int = 9999):
        self.seed_nodes = list(seed_nodes)
        self.max_peers = max_peers
        self.local_port = local_port
        self.known_peers: set = set()

        for addr in seed_nodes:
            self.known_peers.add(addr)

    def add_peer(self, host: str, port: int) -> bool:
        """
        Add a peer to known peers.
        Returns True if it was new, False if duplicate or at max.
        Refuses to add ourselves.
        """
        addr = (host, port)
        if addr in self.known_peers:
            return False
        if self._is_self(host, port):
            return False
        if len(self.known_peers) >= self.max_peers:
            return False
        self.known_peers.add(addr)
        return True

    def remove_peer(self, host: str, port: int) -> None:
        self.known_peers.discard((host, port))

    def get_peers_to_connect(self, connected: set) -> list:
        """Return known peers we're not already connected to."""
        return [addr for addr in self.known_peers if addr not in connected]

    def build_peers_response(self) -> bytes:
        """Build a PEERS payload with our known peers."""
        peers_list = list(self.known_peers)[:self.max_peers]
        return build_peers_payload(peers_list)

    def handle_peers_message(self, payload: bytes) -> list:
        """
        Process a PEERS message payload. Adds new peers.
        Returns list of newly added (host, port) tuples.
        """
        received = parse_peers_payload(payload)
        added = []
        for host, port in received:
            if self.add_peer(host, port):
                added.append((host, port))
        return added

    def _is_self(self, host: str, port: int) -> bool:
        """Check if the address is ourselves."""
        if port != self.local_port:
            return False
        return host in ("127.0.0.1", "0.0.0.0", "localhost")
