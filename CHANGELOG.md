# Changelog

## 0.1.0 — 2026-08-31

First testnet-alpha release of the current protocol.

### Added

- Explicit testnet/devnet namespaces and fail-closed mainnet.
- Canonical transaction/block encodings and interoperability vectors.
- Contextual account-model consensus validation and fixed genesis manifests.
- P2P v2 with chain-aware handshake, bounded messages, sync and relay.
- Authenticated loopback RPC for the Electron wallet.
- Read-only FastAPI explorer service with OpenAPI documentation, lightweight
  core queries and an opt-in, incrementally populated SQLite analytics index.
- Optional one-command Vite wallet server with a narrow server-side RPC gateway.
- Redis nonce reservations, recoverable block persistence and a modern CLI.
- Indexed, cursor-paginated address history and direct block-hash lookup.
- Versioned block locations with bounded offset reads and one-batch lazy
  migration of file-only indexes created by clean protocol-v2 alpha
  directories; crash-orphan recovery now checks only the positions adjacent
  to the current tip instead of rescanning history.
- Honest node readiness and relay receipts with a bounded retry backlog.
- Locked dependency, vulnerability-audit, coverage, distribution-validation and
  isolated wheel-smoke gates in CI for every supported Python version.

### Security

- Testnet is the default and its historical public genesis key is explicitly
  treated as valueless test material.
- RPC tokens and generated wallet files use private local permissions.
- The browser wallet uses a per-process HttpOnly/Strict cookie, local Host and
  Origin/Fetch-Metadata validation, bounded proxy I/O and no CORS; the RPC
  bearer never crosses into browser responses.
- Peer writes have bounded timeouts; relay is concurrent, failed sync peers are
  removed and put into an exponential address cooldown before reconnection.
- Pending replay is bounded by configurable item and total-time budgets per
  peer/cycle; unexpected failures preserve partial counts and remove that peer.
- Confirming a competing sender/nonce transaction atomically prunes both the
  matching Redis reservation and its exact orphaned payload.
- The all-zero destination is rejected instead of acting as an undocumented
  staking/burn sink.
- ECDSA signing and verification now use `coincurve`/libsecp256k1 with compact
  deterministic low-S signatures; the old `python-ecdsa` and `bip32utils`
  dependencies were removed.
- Mainnet cannot initialize until a separately reviewed genesis exists.

### Breaking changes

This release is not compatible with the previous prototype. P2P framing,
hashes, signatures, genesis, chain IDs and the on-disk block format changed.
Python 3.10 is now the minimum supported runtime so the bundled explorer can
use maintained FastAPI/Starlette releases.
Existing chain data must not be reused; follow
[`docs/MIGRATION.md`](docs/MIGRATION.md).
