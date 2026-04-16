from luracoin.network.discovery import PeerDiscovery
from luracoin.network.protocol import build_peers_payload, parse_peers_payload


def test_init_with_seed_nodes():
    d = PeerDiscovery([("10.0.0.1", 9999), ("10.0.0.2", 9999)], max_peers=8)
    assert ("10.0.0.1", 9999) in d.known_peers
    assert ("10.0.0.2", 9999) in d.known_peers
    assert len(d.known_peers) == 2


def test_add_peer_new():
    d = PeerDiscovery([], max_peers=8, local_port=9999)
    assert d.add_peer("10.0.0.1", 9999) is True
    assert ("10.0.0.1", 9999) in d.known_peers


def test_add_peer_duplicate():
    d = PeerDiscovery([], max_peers=8)
    d.add_peer("10.0.0.1", 9999)
    assert d.add_peer("10.0.0.1", 9999) is False


def test_add_peer_max_reached():
    d = PeerDiscovery([], max_peers=2)
    d.add_peer("10.0.0.1", 9999)
    d.add_peer("10.0.0.2", 9999)
    assert d.add_peer("10.0.0.3", 9999) is False
    assert len(d.known_peers) == 2


def test_add_peer_refuses_self():
    d = PeerDiscovery([], max_peers=8, local_port=9999)
    assert d.add_peer("127.0.0.1", 9999) is False
    assert d.add_peer("0.0.0.0", 9999) is False
    assert d.add_peer("localhost", 9999) is False
    # Different port is fine
    assert d.add_peer("127.0.0.1", 8888) is True


def test_remove_peer():
    d = PeerDiscovery([("10.0.0.1", 9999)], max_peers=8)
    d.remove_peer("10.0.0.1", 9999)
    assert ("10.0.0.1", 9999) not in d.known_peers


def test_remove_peer_nonexistent():
    d = PeerDiscovery([], max_peers=8)
    d.remove_peer("10.0.0.1", 9999)  # should not raise


def test_get_peers_to_connect_excludes_connected():
    d = PeerDiscovery(
        [("10.0.0.1", 9999), ("10.0.0.2", 9999), ("10.0.0.3", 9999)],
        max_peers=8,
    )
    connected = {("10.0.0.1", 9999)}
    to_connect = d.get_peers_to_connect(connected)
    assert ("10.0.0.1", 9999) not in to_connect
    assert ("10.0.0.2", 9999) in to_connect
    assert ("10.0.0.3", 9999) in to_connect


def test_get_peers_to_connect_all_connected():
    d = PeerDiscovery([("10.0.0.1", 9999)], max_peers=8)
    connected = {("10.0.0.1", 9999)}
    assert d.get_peers_to_connect(connected) == []


def test_build_peers_response():
    d = PeerDiscovery([("10.0.0.1", 9999), ("10.0.0.2", 8888)], max_peers=8)
    payload = d.build_peers_response()
    parsed = parse_peers_payload(payload)
    assert len(parsed) == 2
    assert set(parsed) == {("10.0.0.1", 9999), ("10.0.0.2", 8888)}


def test_build_peers_response_respects_max():
    seeds = [(f"10.0.0.{i}", 9999) for i in range(20)]
    d = PeerDiscovery(seeds, max_peers=100)
    # Force max_peers to limit the response
    d.max_peers = 5
    payload = d.build_peers_response()
    parsed = parse_peers_payload(payload)
    assert len(parsed) <= 5


def test_handle_peers_message_adds_new():
    d = PeerDiscovery([], max_peers=8, local_port=9999)
    payload = build_peers_payload([("10.0.0.1", 9999), ("10.0.0.2", 8888)])
    added = d.handle_peers_message(payload)
    assert len(added) == 2
    assert ("10.0.0.1", 9999) in d.known_peers
    assert ("10.0.0.2", 8888) in d.known_peers


def test_handle_peers_message_skips_duplicates():
    d = PeerDiscovery([("10.0.0.1", 9999)], max_peers=8, local_port=9999)
    payload = build_peers_payload([("10.0.0.1", 9999), ("10.0.0.2", 8888)])
    added = d.handle_peers_message(payload)
    assert len(added) == 1
    assert ("10.0.0.2", 8888) in added


def test_handle_peers_message_skips_self():
    d = PeerDiscovery([], max_peers=8, local_port=9999)
    payload = build_peers_payload([("127.0.0.1", 9999), ("10.0.0.2", 8888)])
    added = d.handle_peers_message(payload)
    assert len(added) == 1
    assert ("10.0.0.2", 8888) in added
    assert ("127.0.0.1", 9999) not in d.known_peers


def test_handle_peers_message_empty():
    d = PeerDiscovery([], max_peers=8)
    payload = build_peers_payload([])
    added = d.handle_peers_message(payload)
    assert added == []
