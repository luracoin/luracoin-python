import asyncio
import binascii
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luracoin.config import Config
from luracoin.network.node import Node, PROTOCOL_VERSION
from luracoin.network.peer import PeerConnection
from luracoin.network.protocol import (
    CMD_BLOCK,
    CMD_GETBLOCKS,
    CMD_GETPEERS,
    CMD_PEERS,
    CMD_PING,
    CMD_TX,
    HEADER_SIZE,
    INV_TX,
    build_peers_payload,
    build_version_payload,
    parse_inv_payload,
    parse_peers_payload,
    parse_version_payload,
    payload_length_is_valid,
)
from luracoin.transactions import Transaction
from tests.constants import WALLET_1, WALLET_2, WALLET_3


def _mock_streams():
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = MagicMock(spec=asyncio.StreamWriter)
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return reader, writer


def _mock_peer(host, port, height=0):
    peer = MagicMock(spec=PeerConnection)
    peer.host = host
    peer.port = port
    peer.address = (host, port)
    peer.connected = True
    peer.inbound = False
    peer.version_info = {
        "version": PROTOCOL_VERSION,
        "chain_id": Config.CHAIN_ID,
        "height": height,
        "timestamp": 0,
        "listening_port": port,
    }
    peer.send = AsyncMock()
    peer.disconnect = AsyncMock()
    peer.send_ping = AsyncMock(return_value=True)
    return peer


async def _eventually(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_version_commits_to_chain_id():
    payload = build_version_payload(1, 2, 3, 9999, chain_id=17)
    parsed = parse_version_payload(payload)
    assert parsed["version"] == 1
    assert parsed["chain_id"] == 17


def test_node_rejects_foreign_chain_and_protocol():
    node = Node(port=19999, seed_nodes=[])
    compatible = {
        "version": PROTOCOL_VERSION,
        "chain_id": Config.CHAIN_ID,
        "height": 0,
        "timestamp": 0,
        "listening_port": 9998,
    }
    assert node._compatible_version(compatible)
    assert not node._compatible_version({**compatible, "chain_id": 99})
    assert not node._compatible_version({**compatible, "version": 99})
    assert not node._compatible_version({**compatible, "listening_port": 0})


def test_payload_parsers_reject_truncation_and_trailing_bytes():
    with pytest.raises(ValueError):
        parse_version_payload(b"\x00" * 17)
    with pytest.raises(ValueError):
        parse_peers_payload(struct.pack("<H", 2) + b"\x00" * 6)
    with pytest.raises(ValueError):
        parse_inv_payload(bytes([INV_TX]) + b"\x00" * 33)


def test_payload_length_rules_are_command_specific():
    assert payload_length_is_valid(CMD_PING, 8)
    assert not payload_length_is_valid(CMD_PING, 9)
    assert payload_length_is_valid(CMD_BLOCK, 118 + Config.TRANSACTION_LENGTH)
    assert not payload_length_is_valid(CMD_BLOCK, 119)
    assert not payload_length_is_valid(
        CMD_BLOCK, Config.MAX_BLOCK_SERIALIZED_SIZE + 1
    )


@pytest.mark.asyncio
async def test_peer_rejects_oversized_header_before_reading_payload():
    reader, writer = _mock_streams()
    advertised = Config.MAX_P2P_PAYLOAD + 1
    header = (
        Config.MAGIC_BYTES
        + CMD_BLOCK
        + struct.pack("<I", advertised)
        + b"\x00" * 4
    )
    assert len(header) == HEADER_SIZE
    reader.readexactly = AsyncMock(return_value=header)
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)

    command, payload = await peer.receive()

    assert (command, payload) == (None, None)
    assert reader.readexactly.await_count == 1
    assert peer.disconnect_reason == "invalid payload length"


@pytest.mark.asyncio
async def test_peer_rejects_malformed_outbound_payload():
    reader, writer = _mock_streams()
    peer = PeerConnection(reader, writer, "10.0.0.1", 9999)

    with pytest.raises(ValueError):
        await peer.send(CMD_PING, b"short")
    writer.write.assert_not_called()


def test_known_inventory_is_bounded():
    node = Node(port=19999, seed_nodes=[])
    with patch.object(Config, "KNOWN_INV_LIMIT", 3):
        for value in range(5):
            node._remember_inventory(bytes([value]) * 32)

    assert len(node.known_invs) == 3
    assert bytes([0]) * 32 not in node.known_invs
    assert bytes([4]) * 32 in node.known_invs


def _relay_test_transaction():
    return Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=1,
        from_address="0" * 34,
        to_address="1" * 34,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )


@pytest.mark.asyncio
async def test_transaction_with_zero_peers_is_replayed_after_peer_connects():
    node = Node(port=19999, seed_nodes=[])
    transaction = _relay_test_transaction()
    hash_bytes = binascii.unhexlify(transaction.id)

    assert await node.broadcast_tx(transaction) == 0
    assert node._pending_tx_relays[hash_bytes] == transaction.serialize()
    assert (INV_TX, hash_bytes) not in node._relayed_invs

    chain = MagicMock()
    chain.tip = 0
    chain.get_block_file_number.return_value = 0
    node.chain = chain
    node.block_sync.chain = chain
    peer = _mock_peer("10.0.0.8", 9998, height=0)
    node.peers[peer.address] = peer

    await node._post_handshake(peer)

    assert peer.send.await_args_list[0].args[0] == CMD_GETPEERS
    peer.send.assert_any_await(CMD_TX, transaction.serialize())
    assert (INV_TX, hash_bytes) in node._relayed_invs


@pytest.mark.asyncio
async def test_higher_peer_handshake_interrupts_stale_work():
    node = Node(port=19999, seed_nodes=[])
    chain = MagicMock()
    chain.tip = 0
    node.chain = chain
    node.block_sync.chain = chain
    peer = _mock_peer("10.0.0.9", 9998, height=1)
    callback = MagicMock()
    node.on_sync_needed = callback

    with patch.object(node, "_schedule_best_peer_sync", return_value=True):
        await node._post_handshake(peer)

    callback.assert_called_once_with()


@pytest.mark.asyncio
async def test_transaction_relay_counts_only_successful_peers():
    node = Node(port=19999, seed_nodes=[])
    successful = _mock_peer("10.0.0.1", 9999)
    failing = _mock_peer("10.0.0.2", 9999)
    failing.send.side_effect = OSError("connection closed")
    node.peers[successful.address] = successful
    node.peers[failing.address] = failing

    relay_count = await node.broadcast_tx(_relay_test_transaction())

    assert relay_count == 1
    successful.send.assert_awaited_once()
    assert failing.address not in node.peers


@pytest.mark.asyncio
async def test_pending_transaction_relay_backlog_is_bounded():
    node = Node(port=19999, seed_nodes=[])

    with patch.object(Config, "PENDING_TX_RELAY_LIMIT", 2):
        transactions = []
        for nonce in range(3):
            transaction = _relay_test_transaction()
            transaction.nonce = nonce
            transactions.append(transaction)
            assert await node.broadcast_tx(transaction) == 0

        assert len(node._pending_tx_relays) == 2
        oldest_hash = binascii.unhexlify(transactions[0].id)
        assert oldest_hash not in node._pending_tx_relays


@pytest.mark.asyncio
async def test_failed_sync_peer_is_removed_before_another_is_selected():
    node = Node(port=19999, seed_nodes=[])
    node.running = True
    chain = MagicMock()
    chain.tip = 0
    chain.get_block_file_number.return_value = 0
    node.chain = chain
    node.block_sync.chain = chain

    bad = _mock_peer("10.0.0.10", 9999, height=10)
    good = _mock_peer("10.0.0.11", 9999, height=5)
    bad_queue = MagicMock()
    bad_queue.empty.return_value = True
    bad_queue.get = AsyncMock(side_effect=asyncio.TimeoutError)
    node.peers = {bad.address: bad, good.address: good}
    node._peer_addresses = {bad: bad.address, good: good.address}
    node._sync_queues = {bad: bad_queue, good: asyncio.Queue()}
    node._sync_tasks[bad] = asyncio.current_task()

    with (
        patch.object(
            node, "_schedule_best_peer_sync", return_value=False
        ) as schedule_next,
    ):
        await node._sync_from_peer(bad)

    assert bad.address not in node.peers
    assert good.address in node.peers
    bad.disconnect.assert_awaited_once()
    schedule_next.assert_called_once()
    assert node._sync_cooldown_active(bad.address)


@pytest.mark.asyncio
async def test_sync_cooldown_backs_off_and_excludes_reconnect_and_selection():
    node = Node(port=19999, seed_nodes=[])
    node.running = True
    bad = _mock_peer("10.0.0.10", 9999, height=10)
    good = _mock_peer("10.0.0.11", 9999, height=5)
    node.peers = {bad.address: bad, good.address: good}
    node._peer_addresses = {bad: bad.address, good: good.address}
    node._sync_queues = {bad: asyncio.Queue(), good: asyncio.Queue()}

    with (
        patch.object(Config, "SYNC_PEER_COOLDOWN_BASE", 10.0),
        patch.object(Config, "SYNC_PEER_COOLDOWN_MAX", 40.0),
        patch("luracoin.network.node.time.monotonic", return_value=100.0),
    ):
        assert node._record_sync_failure(bad.address) == 10.0
        assert node._record_sync_failure(bad.address) == 20.0
        assert node._sync_cooldown_active(bad.address)
        assert node._sync_cooldown_active((bad.host, bad.port + 1))

        with patch.object(
            node, "_schedule_sync", return_value=True
        ) as schedule:
            assert node._schedule_best_peer_sync()
        schedule.assert_called_once_with(good)

        with patch(
            "luracoin.network.node.asyncio.open_connection",
            new_callable=AsyncMock,
        ) as open_connection:
            assert not await node.connect_to_peer(bad.host, bad.port + 1)
        open_connection.assert_not_awaited()

    assert not node._sync_cooldown_active(bad.address, now=121.0)


def test_sync_cooldown_normalizes_ipv6_and_bounds_address_history():
    node = Node(port=19999, seed_nodes=[])

    with (
        patch.object(Config, "SYNC_PEER_COOLDOWN_BASE", 10.0),
        patch.object(Config, "SYNC_PEER_COOLDOWN_LIMIT", 2),
    ):
        node._record_sync_failure(("[2001:DB8::1]", 1000), now=100.0)
        assert node._sync_cooldown_active(("2001:db8::1", 2000), now=100.0)

        node._record_sync_failure(("10.0.0.1", 1000), now=100.0)
        node._record_sync_failure(("10.0.0.2", 1000), now=100.0)

    assert not node._sync_cooldown_active(("2001:db8::1", 3000), now=100.0)
    assert len(node._sync_peer_failures) == 2
    assert len(node._sync_peer_cooldowns) == 2


@pytest.mark.asyncio
async def test_disconnect_during_incomplete_sync_records_cooldown():
    node = Node(port=19999, seed_nodes=[])
    node.running = True
    chain = MagicMock()
    chain.tip = 0
    chain.get_block_file_number.return_value = 0
    node.chain = chain
    node.block_sync.chain = chain
    peer = _mock_peer("10.0.0.12", 9999, height=2)
    node.peers = {peer.address: peer}
    node._peer_addresses = {peer: peer.address}
    node._sync_queues = {peer: asyncio.Queue()}

    with patch.object(node, "_schedule_best_peer_sync", return_value=False):
        task = asyncio.create_task(node._sync_from_peer(peer))
        node._sync_tasks[peer] = task
        await _eventually(lambda: peer.send.await_count == 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert node._sync_cooldown_active((peer.host, peer.port + 1))
    assert peer.address not in node.peers
    peer.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_slow_peer_does_not_block_relay_to_healthy_peer():
    node = Node(port=19999, seed_nodes=[])
    slow = _mock_peer("10.0.0.20", 9999)
    healthy = _mock_peer("10.0.0.21", 9999)

    async def never_finishes(*_args):
        await asyncio.Future()

    slow.send.side_effect = never_finishes
    node.peers = {slow.address: slow, healthy.address: healthy}
    with patch.object(Config, "P2P_SEND_TIMEOUT", 0.01):
        count = await node._send_to_peers(CMD_TX, b"payload")

    assert count == 1
    healthy.send.assert_awaited_once_with(CMD_TX, b"payload")
    assert slow.address not in node.peers


@pytest.mark.asyncio
async def test_unexpected_peer_error_preserves_successful_relay_count():
    node = Node(port=19999, seed_nodes=[])
    broken = _mock_peer("10.0.0.22", 9999)
    healthy = _mock_peer("10.0.0.23", 9999)
    broken.send.side_effect = RuntimeError("unexpected writer failure")
    node.peers = {broken.address: broken, healthy.address: healthy}

    count = await node._send_to_peers(CMD_TX, b"payload")

    assert count == 1
    healthy.send.assert_awaited_once_with(CMD_TX, b"payload")
    assert broken.address not in node.peers


@pytest.mark.asyncio
async def test_pending_replay_uses_configured_batch_and_cursor():
    node = Node(port=19999, seed_nodes=[])
    peer = _mock_peer("10.0.0.24", 9999)
    transactions = []
    for nonce in range(3):
        transaction = _relay_test_transaction()
        transaction.nonce = nonce
        transactions.append(transaction)
        node._queue_pending_transaction(
            transaction.serialize(), binascii.unhexlify(transaction.id)
        )

    with (
        patch.object(Config, "PENDING_TX_REPLAY_BATCH_SIZE", 2),
        patch.object(Config, "PENDING_TX_REPLAY_BUDGET", 1.0),
    ):
        first = await node._relay_pending_to_peer(peer)
        second = await node._relay_pending_to_peer(peer)

    assert first == (2, True)
    assert second == (1, True)
    assert [call.args[1] for call in peer.send.await_args_list] == [
        transaction.serialize() for transaction in transactions
    ]


@pytest.mark.asyncio
async def test_pending_replay_budget_removes_slow_peer_promptly():
    node = Node(port=19999, seed_nodes=[])
    slow = _mock_peer("10.0.0.25", 9999)

    async def never_finishes(*_args):
        await asyncio.Future()

    slow.send.side_effect = never_finishes
    node.peers = {slow.address: slow}
    transaction = _relay_test_transaction()
    node._queue_pending_transaction(
        transaction.serialize(), binascii.unhexlify(transaction.id)
    )
    started = asyncio.get_running_loop().time()
    with (
        patch.object(Config, "P2P_SEND_TIMEOUT", 1.0),
        patch.object(Config, "PENDING_TX_REPLAY_BUDGET", 0.01),
    ):
        count = await node._relay_pending_transactions()
    elapsed = asyncio.get_running_loop().time() - started

    assert count == 0
    assert elapsed < 0.2
    assert slow.address not in node.peers


@pytest.mark.asyncio
async def test_pending_replay_preserves_partial_count_on_unexpected_error():
    node = Node(port=19999, seed_nodes=[])
    flaky = _mock_peer("10.0.0.26", 9999)
    healthy = _mock_peer("10.0.0.27", 9999)
    attempts = 0

    async def fail_after_one(*_args):
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            raise RuntimeError("unexpected replay failure")

    flaky.send.side_effect = fail_after_one
    node.peers = {flaky.address: flaky, healthy.address: healthy}
    for nonce in range(3):
        transaction = _relay_test_transaction()
        transaction.nonce = nonce
        node._queue_pending_transaction(
            transaction.serialize(), binascii.unhexlify(transaction.id)
        )

    with (
        patch.object(Config, "PENDING_TX_REPLAY_BATCH_SIZE", 3),
        patch.object(Config, "PENDING_TX_REPLAY_BUDGET", 1.0),
    ):
        count = await node._relay_pending_transactions()

    assert count == 4
    assert flaky.address not in node.peers
    assert healthy.address in node.peers


def test_confirmed_sender_nonce_prunes_relay_and_redis_candidate():
    local = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=10,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(binascii.unhexlify(WALLET_1["private_key"]))
    confirmed = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=9,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    ).sign(binascii.unhexlify(WALLET_1["private_key"]))
    node = Node(port=19999, seed_nodes=[])
    local_hash = binascii.unhexlify(local.id)
    node._queue_pending_transaction(local.serialize(), local_hash)

    redis_client = MagicMock()
    with patch("luracoin.network.node.redis.Redis", return_value=redis_client):
        node._forget_confirmed_transactions(MagicMock(txns=[confirmed]))

    assert local_hash not in node._pending_tx_relays
    redis_client.eval.assert_called_once()
    args = redis_client.eval.call_args.args
    assert args[1:] == (
        2,
        local.mempool_nonce_key,
        local.id,
        local.id,
        local.serialize(),
    )


def test_confirmed_sender_nonce_snapshots_candidate_outside_relay_cache():
    local = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=10,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    ).sign(binascii.unhexlify(WALLET_1["private_key"]))
    confirmed = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=9,
        from_address=WALLET_1["address"],
        to_address=WALLET_3["address"],
    ).sign(binascii.unhexlify(WALLET_1["private_key"]))
    block = MagicMock(txns=[confirmed])
    node = Node(port=19999, seed_nodes=[])
    redis_client = MagicMock()
    redis_client.mget.side_effect = [
        [local.id.encode("ascii")],
        [local.serialize()],
    ]
    redis_client.eval.return_value = 1

    with patch("luracoin.network.node.redis.Redis", return_value=redis_client):
        captured = node._snapshot_competing_transactions(block)
        node._forget_confirmed_transactions(block, captured)

    assert not node._pending_tx_relays
    assert len(captured) == 1
    assert captured[0][0].id == local.id
    assert captured[0][1] == local.serialize()
    assert redis_client.mget.call_args_list[0].args == (
        [confirmed.mempool_nonce_key],
    )
    assert redis_client.mget.call_args_list[1].args == ([local.id],)
    redis_client.eval.assert_called_once()
    eviction_args = redis_client.eval.call_args.args
    assert eviction_args[1:] == (
        2,
        local.mempool_nonce_key,
        local.id,
        local.id,
        local.serialize(),
    )


def test_ready_uses_best_connected_peer_height_but_allows_isolation():
    node = Node(port=19999, seed_nodes=[])
    chain = MagicMock()
    chain.tip = 5
    chain.get_block_file_number.return_value = 0
    node.chain = chain
    node.block_sync.chain = chain
    behind = _mock_peer("10.0.0.1", 9999, height=4)
    ahead = _mock_peer("10.0.0.2", 9999, height=8)
    node.peers[behind.address] = behind
    node.peers[ahead.address] = ahead

    assert node.best_peer_height == 8
    assert node.ready is False

    chain.tip = 8
    assert node.ready is True

    pending_sync = MagicMock()
    pending_sync.done.return_value = False
    node._sync_tasks[ahead] = pending_sync
    node.block_sync.syncing = False
    assert node.syncing is True
    assert node.ready is False
    node._sync_tasks.clear()

    chain.tip = 5
    node.peers.clear()
    assert node.best_peer_height == 5
    assert node.ready is True


@pytest.mark.asyncio
async def test_sync_continues_with_most_advanced_waiting_peer():
    node = Node(port=19999, seed_nodes=[])
    node.running = True
    chain = MagicMock()
    chain.tip = 0
    chain.get_block_file_number.return_value = 0
    node.chain = chain
    node.block_sync.chain = chain
    lower = _mock_peer("10.0.0.1", 9999, height=1)
    higher = _mock_peer("10.0.0.2", 9999, height=3)
    lower_queue = asyncio.Queue()
    higher_queue = asyncio.Queue()
    node.peers[lower.address] = lower
    node.peers[higher.address] = higher
    node._sync_queues[lower] = lower_queue
    node._sync_queues[higher] = higher_queue
    requested = []

    async def lower_send(command, _payload=b""):
        if command == CMD_GETBLOCKS:
            requested.append(lower)
            chain.tip = 1
            lower_queue.put_nowait(True)

    async def higher_send(command, _payload=b""):
        if command == CMD_GETBLOCKS:
            requested.append(higher)
            chain.tip = 3
            higher_queue.put_nowait(True)
            higher_queue.put_nowait(True)

    lower.send.side_effect = lower_send
    higher.send.side_effect = higher_send

    assert node._schedule_sync(lower)
    await _eventually(
        lambda: chain.tip == 3
        and not any(not task.done() for task in node._sync_tasks.values())
    )

    assert requested == [lower, higher]
    assert node.best_peer_height == 3
    assert node.ready is True
    node.running = False


@pytest.mark.asyncio
async def test_received_transaction_relays_except_to_source():
    node = Node(port=19999, seed_nodes=[])
    source = _mock_peer("10.0.0.1", 9999)
    target = _mock_peer("10.0.0.2", 9999)
    node.peers[source.address] = source
    node.peers[target.address] = target
    transaction = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=1,
        from_address="0" * 34,
        to_address="1" * 34,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    payload = transaction.serialize()

    with patch.object(node, "_handle_tx", return_value=True):
        await node.handle_message(source, CMD_TX, payload)

    source.send.assert_not_called()
    target.send.assert_awaited_once_with(CMD_TX, payload)


@pytest.mark.asyncio
async def test_peers_message_can_interleave_with_active_sync():
    node = Node(port=19999, seed_nodes=[], max_peers=8)
    node.running = True
    peer = _mock_peer("10.0.0.1", 9999, height=1)
    queue = asyncio.Queue()
    node._sync_queues[peer] = queue
    sync_task = asyncio.create_task(node._sync_from_peer(peer))
    node._sync_tasks[peer] = sync_task

    await _eventually(
        lambda: any(
            call.args and call.args[0] == CMD_GETBLOCKS
            for call in peer.send.await_args_list
        )
    )
    await node.handle_message(
        peer, CMD_PEERS, build_peers_payload([("10.0.0.2", 9998)])
    )

    assert ("10.0.0.2", 9998) in node.discovery.known_peers
    assert not sync_task.done()
    queue.put_nowait(False)
    await sync_task
    node.running = False


@pytest.mark.asyncio
async def test_peers_message_rejects_own_docker_socket_address():
    node = Node(port=9999, seed_nodes=[], max_peers=8)
    peer = _mock_peer("luracoin-fullnode-node", 9999)
    _reader, writer = _mock_streams()
    writer.get_extra_info.side_effect = lambda name: {
        "sockname": ("172.18.0.4", 38916),
        "peername": ("172.18.0.2", 9999),
    }.get(name)
    peer.writer = writer

    await node.handle_message(
        peer,
        CMD_PEERS,
        build_peers_payload([("172.18.0.4", 9999), ("172.18.0.3", 9999)]),
    )

    assert "172.18.0.4" in node.discovery.local_addresses
    assert ("172.18.0.4", 9999) not in node.discovery.known_peers
    assert ("172.18.0.3", 9999) in node.discovery.known_peers


@pytest.mark.asyncio
async def test_dns_alias_resolving_to_own_listener_is_not_activated():
    alias = "this-node-dns-alias"
    node = Node(port=9999, seed_nodes=[(alias, 9999)])
    node.running = True
    peer = _mock_peer(alias, 9999)
    _reader, writer = _mock_streams()
    writer.get_extra_info.side_effect = lambda name: {
        "sockname": ("172.18.0.4", 39778),
        "peername": ("172.18.0.4", 9999),
    }.get(name)
    peer.writer = writer

    assert not await node._activate_peer(peer, (alias, 9999))
    assert not node.peers
    assert (alias, 9999) not in node.discovery.known_peers
    assert "172.18.0.4" in node.discovery.local_addresses
    node.running = False


@pytest.mark.asyncio
async def test_two_nodes_handshake_dispatch_ping_and_shutdown_over_tcp():
    first = Node(host="127.0.0.1", port=0, seed_nodes=[], ping_interval=3600)
    second = Node(host="127.0.0.1", port=0, seed_nodes=[], ping_interval=3600)
    await first.start()
    await second.start()
    try:
        assert await second.connect_to_peer("127.0.0.1", first.port)
        await _eventually(lambda: len(first.peers) == len(second.peers) == 1)
        assert len(first._reader_tasks) == len(second._reader_tasks) == 1
        assert ("127.0.0.1", first.port) not in first.discovery.known_peers
        assert ("127.0.0.1", second.port) not in second.discovery.known_peers

        # PONG is consumed by each node's existing dispatcher, not a second
        # direct read from PeerConnection.send_ping.
        await second.ping_peers()
        assert len(first.peers) == len(second.peers) == 1
    finally:
        await second.stop()
        await first.stop()

    assert first._server is second._server is None
    assert not first._reader_tasks and not second._reader_tasks
    assert not first._pong_waiters and not second._pong_waiters


@pytest.mark.asyncio
async def test_inbound_connection_limit_is_enforced():
    server = Node(
        host="127.0.0.1",
        port=0,
        seed_nodes=[],
        max_peers=4,
        max_inbound_peers=1,
        ping_interval=3600,
    )
    first = Node(host="127.0.0.1", port=0, seed_nodes=[], ping_interval=3600)
    second = Node(host="127.0.0.1", port=0, seed_nodes=[], ping_interval=3600)
    await server.start()
    await first.start()
    await second.start()
    try:
        assert await first.connect_to_peer("127.0.0.1", server.port)
        await _eventually(lambda: len(server.peers) == 1)
        assert not await second.connect_to_peer("127.0.0.1", server.port)
        assert len(server.peers) == 1
    finally:
        await second.stop()
        await first.stop()
        await server.stop()
