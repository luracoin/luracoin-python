import binascii
import json
import logging
import os
import random
import socket
import socketserver
import threading
import time
from typing import Iterable, Mapping, NamedTuple, get_type_hints

import redis

from .config import Config
from .serialize import deserialize_transaction

mempool_db = redis.StrictRedis(host="localhost", port=6379, db=0)

# =========================================================
# =========================================================
# DELETE THIS. This is only here to prevent from failing since
# this is a temporal file and still in WIP.

locate_block = None
active_chain = None
chain_lock = None
active_chain = None
locate_block = None
connect_block = None
active_chain = None
chain_lock = None
utxo_set = None
active_chain = None

# =========================================================
# =========================================================


logging.basicConfig(
    level=getattr(logging, os.environ.get("TC_LOG_LEVEL", "INFO")),
    format="[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

mempool = {
    "abc123": "content1",
    "abc456": "content2",
    "abc789": "content3",
    "def123": "content4",
    "def456": "content5",
    "def789": "content6",
}

peer_hostnames = {p for p in os.environ.get("TC_PEERS", "").split(",") if p}

# Signal when the initial block download has completed.
ibd_done = threading.Event()


class GetBlocksMsg(NamedTuple):  # Request blocks during initial sync
    """
    See https://bitcoin.org/en/developer-guide#blocks-first
    """

    from_blockid: str

    CHUNK_SIZE = 50

    def handle(self, sock, peer_hostname):
        logger.debug(f"[p2p] recv getblocks from {peer_hostname}")

        _, height, _ = locate_block(self.from_blockid, active_chain)

        # If we don't recognize the requested hash as part of the active
        # chain, start at the genesis block.
        height = height or 1

        with chain_lock:
            blocks = active_chain[height : (height + self.CHUNK_SIZE)]

        logger.debug(f"[p2p] sending {len(blocks)} to {peer_hostname}")
        send_to_peer(InvMsg(blocks), peer_hostname)


class InvMsg(NamedTuple):  # Convey blocks to a peer who is doing initial sync
    blocks: Iterable[str]

    def handle(self, sock, peer_hostname):
        logger.info(f"[p2p] recv inv from {peer_hostname}")

        new_blocks = [b for b in self.blocks if not locate_block(b.id)[0]]

        if not new_blocks:
            logger.info("[p2p] initial block download complete")
            ibd_done.set()
            return

        for block in new_blocks:
            connect_block(block)

        new_tip_id = active_chain[-1].id
        logger.info(f"[p2p] continuing initial block download at {new_tip_id}")

        with chain_lock:
            # "Recursive" call to continue the initial block sync.
            send_to_peer(GetBlocksMsg(new_tip_id))


class GetUTXOsMsg(NamedTuple):  # List all UTXOs
    def handle(self, sock, peer_hostname):
        sock.sendall(encode_socket_data(list(utxo_set.items())))


class GetMempoolMsg(NamedTuple):  # List the mempool
    def handle(self, sock, peer_hostname):
        sock.sendall(encode_socket_data(list(mempool.keys())))


class GetActiveChainMsg(NamedTuple):  # Get the active chain in its entirety.
    def handle(self, sock, peer_hostname):
        sock.sendall(encode_socket_data(list(active_chain)))


class AddPeerMsg(NamedTuple):
    peer_hostname: str

    def handle(self, sock, peer_hostname):
        peer_hostnames.add(self.peer_hostname)


def read_all_from_socket(req) -> object:
    data = b""
    # Our protocol is: first 4 bytes signify msg length.
    msg_len = int(binascii.hexlify(req.recv(4) or b"\x00"), 16)

    while msg_len > 0:
        tdat = req.recv(1024)
        data += tdat
        msg_len -= len(tdat)

    return deserialize(data.decode()) if data else None


def send_to_peer(data, peer=None):
    """Send a message to a (by default) random peer."""
    global peer_hostnames

    peer = peer or random.choice(list(peer_hostnames))
    tries_left = 3

    while tries_left > 0:
        try:
            with socket.create_connection((peer, Config.PORT), timeout=1) as s:
                s.sendall(encode_socket_data(data))
        except Exception:
            logger.exception(f"failed to send to peer {peer}")
            tries_left -= 1
            time.sleep(2)
        else:
            return

    logger.info(f"[p2p] removing dead peer {peer}")
    peer_hostnames = {x for x in peer_hostnames if x != peer}


def int_to_8bytes(a: int) -> bytes:
    return binascii.unhexlify(f"{a:0{8}x}")


def encode_socket_data(data: object) -> bytes:
    """Our protocol is: first 4 bytes signify msg length."""
    to_send = serialize(data).encode()
    return int_to_8bytes(len(to_send)) + to_send


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def serialize(obj) -> str:
    """NamedTuple-flavored serialization to JSON."""

    def contents_to_primitive(o):
        if hasattr(o, "_asdict"):
            o = {**o._asdict(), "_type": type(o).__name__}
        elif isinstance(o, (list, tuple)):
            return [contents_to_primitive(i) for i in o]
        elif isinstance(o, bytes):
            return binascii.hexlify(o).decode()
        elif not isinstance(o, (dict, bytes, str, int, type(None))):
            raise ValueError(f"Can't serialize {o}")

        if isinstance(o, Mapping):
            for k, v in o.items():
                o[k] = contents_to_primitive(v)

        return o

    return json.dumps(
        contents_to_primitive(obj), sort_keys=True, separators=(",", ":")
    )


def deserialize(serialized: str) -> object:
    """NamedTuple-flavored serialization from JSON."""
    gs = globals()

    def contents_to_objs(o):
        if isinstance(o, list):
            return [contents_to_objs(i) for i in o]
        elif not isinstance(o, Mapping):
            return o

        _type = gs[o.pop("_type", None)]
        bytes_keys = {
            k for k, v in get_type_hints(_type).items() if v == bytes
        }

        for k, v in o.items():
            o[k] = contents_to_objs(v)

            if k in bytes_keys:
                o[k] = binascii.unhexlify(o[k]) if o[k] else o[k]

        return _type(**o)

    return contents_to_objs(json.loads(serialized))


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = read_all_from_socket(self.request)
        peer_hostname = self.request.getpeername()[0]
        peer_hostnames.add(peer_hostname)

        logger.info(f"received msg...")
        if data[0:8] == Config.MAGIC_BYTES:
            if data[8:32] == "74786e000000000000000000":
                tx = deserialize_transaction("01" + data[32:])
                mempool_db.set(tx[0].id, tx[0])

            """
            if hasattr(data, 'handle') and isinstance(data.handle, Callable):
                logger.info(f'received msg {data} from peer {peer_hostname}')
                data.handle(self.request, peer_hostname)
            elif isinstance(data, Transaction):
                logger.info(f"
                    received txn {data.id} from peer {peer_hostname}")
                add_txn_to_mempool(data)
            elif isinstance(data, Block):
                logger.info(f"
                    received block {data.id} from peer {peer_hostname}")
                connect_block(data)
            """
