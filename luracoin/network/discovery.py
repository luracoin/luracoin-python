"""
Peer discovery: seed nodes + peer exchange.
"""

import ipaddress

from luracoin.network.protocol import (
    MAX_PEER_ADDRESSES,
    build_peers_payload,
    parse_peers_payload,
)


class PeerDiscovery:
    """Tracks known peers and manages peer exchange."""

    def __init__(
        self, seed_nodes: list, max_peers: int = 8, local_port: int = 9999
    ):
        self.seed_nodes = list(seed_nodes)
        self.max_peers = max_peers
        self.local_port = local_port
        self.known_peers: set = set()
        self.local_addresses = {"127.0.0.1"}

        for host, port in seed_nodes:
            self.add_peer(host, port)

    def add_peer(self, host: str, port: int) -> bool:
        """
        Add a peer to known peers.
        Returns True if it was new, False if duplicate or at max.
        Refuses to add ourselves.
        """
        host = self._normalize_connect_host(host)
        if host is None or not self._valid_port(port):
            return False
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
        return [
            addr
            for addr in self.known_peers
            if addr not in connected and not self._is_self(*addr)
        ]

    def add_local_address(self, host: str) -> bool:
        """Remember an IP observed on one of this node's own sockets."""

        try:
            address = ipaddress.ip_address(host)
        except (ValueError, TypeError):
            return False
        if address.is_unspecified:
            return False
        normalized = str(address)
        was_new = normalized not in self.local_addresses
        self.local_addresses.add(normalized)
        self.known_peers.discard((normalized, self.local_port))
        return was_new

    def build_peers_response(self) -> bytes:
        """Build a PEERS payload from serializable IPv4 endpoints only.

        DNS seed names remain in ``known_peers`` so this node can connect to
        them, but the v2 wire format has room only for IPv4 literals.  Invalid
        or connection-only addresses must not make GETPEERS tear down an
        otherwise healthy peer connection.
        """

        limit = max(0, min(self.max_peers, MAX_PEER_ADDRESSES))
        if limit == 0:
            return build_peers_payload([])
        peers_list = []
        for peer in self.known_peers:
            if not isinstance(peer, tuple) or len(peer) != 2:
                continue
            host, port = peer
            if not self._valid_port(port):
                continue
            try:
                address = ipaddress.IPv4Address(host)
            except (ipaddress.AddressValueError, TypeError):
                continue
            if not self._is_advertisable_address(address):
                continue
            peers_list.append((str(address), port))
            if len(peers_list) >= limit:
                break
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
        if isinstance(host, str) and host.casefold() == "localhost":
            return True
        try:
            address = ipaddress.ip_address(host)
        except (ValueError, TypeError):
            return False
        return address.is_unspecified or str(address) in self.local_addresses

    @staticmethod
    def _normalize_connect_host(host: str):
        """Normalize IP literals while retaining valid DNS names."""

        if (
            not isinstance(host, str)
            or not host
            or host != host.strip()
            or any(character.isspace() for character in host)
        ):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # A dotted numeric value is intended to be IPv4, not a DNS name.
            if all(
                character.isdigit() or character == "." for character in host
            ):
                return None
            return host
        if not PeerDiscovery._is_advertisable_address(address):
            return None
        return str(address)

    @staticmethod
    def _is_advertisable_address(address) -> bool:
        return not (
            address.is_unspecified
            or address.is_multicast
            or address.is_reserved
        )

    @staticmethod
    def _valid_port(port) -> bool:
        return (
            isinstance(port, int)
            and not isinstance(port, bool)
            and 1 <= port <= 0xFFFF
        )
