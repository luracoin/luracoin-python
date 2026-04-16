# P2P Network Protocol Design

## Overview

Binary protocol over TCP with asyncio, seed nodes + peer discovery, sequential block sync.

## Protocol

Each message: `magic_bytes(4B) + command(12B padded \x00) + payload_length(4B) + checksum(4B) + payload`

- `magic_bytes`: `\xbaw\xd8\x9f` (from Config)
- `checksum`: first 4 bytes of sha256d(payload)

## Commands

| Command | Direction | Payload |
|---------|-----------|---------|
| `version` | bidirectional | version(4B) + height(4B) + timestamp(4B) + listening_port(2B) |
| `verack` | response | empty |
| `getpeers` | request | empty |
| `peers` | response | count(2B) + [ip(4B) + port(2B)] * N |
| `getblocks` | request | start_height(4B) + count(2B) |
| `block` | response/broadcast | serialized block (existing format) |
| `tx` | broadcast | serialized transaction (existing format) |
| `inv` | broadcast | type(1B) + hash(32B) |
| `getdata` | request | type(1B) + hash(32B) |
| `ping` | request | nonce(8B) |
| `pong` | response | nonce(8B) |

## Architecture

```
luracoin/network/
    __init__.py
    protocol.py   -- Message serialization/deserialization
    peer.py       -- Single peer connection (asyncio StreamReader/StreamWriter)
    node.py       -- Server: manages peers, dispatches messages
    sync.py       -- Block synchronization logic
    discovery.py  -- Seed nodes + peer exchange
```

## Flow

1. Node starts, listens on Config.PORT (9999)
2. Connects to hardcoded seed nodes
3. Handshake: send `version` (with chain height) -> receive `verack`
4. Discovery: send `getpeers` -> receive `peers` -> connect to new peers
5. Sync: if peer has greater height, send `getblocks` -> receive blocks sequentially
6. Normal operation:
   - Mine block -> `inv` to all peers
   - Receive `inv` -> if unknown, `getdata` -> receive `block` -> validate and save
   - Receive `tx` -> validate and add to mempool
7. Keep-alive: periodic `ping`/`pong`, disconnect dead peers

## Config

```python
SEED_NODES = [("127.0.0.1", 9999)]
MAX_PEERS = 8
PING_INTERVAL = 60
SYNC_BATCH_SIZE = 50
```

## Testing Strategy

- **protocol.py**: serialize/deserialize each command, checksums, magic bytes, roundtrip
- **peer.py**: mock StreamReader/StreamWriter, handshake, timeout handling
- **node.py**: simulated multiple peers, message dispatch
- **sync.py**: sync with ahead node, already-synced case, invalid blocks rejected
- **discovery.py**: peer exchange, no duplicates, max peers enforcement
