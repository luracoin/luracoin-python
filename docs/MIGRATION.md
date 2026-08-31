# Migration to protocol v2 testnet alpha

The current chain is a clean test network, not an in-place upgrade. Old block
files, RocksDB state and Redis mempool entries are incompatible.

1. Back up only recovery material you intentionally want to keep. A mnemonic
   or private key is sufficient; never publish it or commit it.
2. Stop every old node, miner and wallet process.
3. Keep the old data directory as a read-only backup. Start v2 with a new,
   empty directory, for example:

   ```sh
   luracoin node --network testnet --data-dir ~/.luracoin/testnet-v2
   ```

4. Point Electron at that exact directory by exporting
   `LURACOIN_DATA_DIR=~/.luracoin/testnet-v2` before it starts.
5. Do not connect v1 peers to v2. Every peer must use protocol version 2 and
   the same chain ID.
6. Treat every old test balance and transaction ID as obsolete. The v2 node
   starts from its fixed testnet genesis and rebuilds state from v2 blocks.

Within a clean v2 alpha directory, early four-byte `height -> block file`
index entries are upgraded lazily to versioned `file + offset + length`
locations. The first legacy read scans its indexed file and upgrades every
legacy entry represented by that file in one database batch, so later pages do
not repeat the scan. This narrowly scoped compatibility is safe because the v2
block serialization is unchanged. It must not be used to open a v1/prototype
directory, whose files remain incompatible.

There is no mainnet migration: mainnet is intentionally undefined and cannot
initialize. There is also no reorganization/reindex command yet, so preserving
the old directory is safer than attempting an in-place conversion.
