# Luracoin - Pending tasks

> **Model:** Account Model (not UTXO). Each address has balance + nonce.
> **Decisions made:** Staking and Burn Transactions are deferred.
> **`chain` field:** Distinguishes mainnet (0) vs testnet (1).

---

## 1. Bugs and critical issues -- DONE

- [x] **1.1** Fix signature verification security bug
- [x] **1.2** Fix malformed byte in test genesis block
- [x] **1.3** Fix `database_name` type inconsistency
- [x] **1.4** Remove debug `print()` calls
- [x] **1.5** Fix mutable default argument in `Block.__init__`
- [x] **Extra:** Migrated to `rocksdict`, fixed conftest fixture

## 2. Transactions -- DONE

- [x] **2.1** Add `from_address` field to Transaction
- [x] **2.2** Implement `Transaction.save()`
- [x] **2.3** Implement sender balance validation
- [x] **2.4** Implement replay attack protection with nonce

## 3. Blocks -- DONE

- [x] **3.1** Complete `Block.validate()` -- PoW, coin supply, block size, timestamp, height
- [x] **3.2** Complete `Block.save()` -- saves txns, credits miner, cleans mempool
- [x] **3.3** Implement `Block.create()` -- full flow: coinbase + PoW + save
- [x] **3.4** Implement dynamic difficulty adjustment -- `calculate_new_bits()` in helpers

## 4. Chain state -- DONE

- [x] **4.1** Define account structure -- `{"balance": 0, "nonce": 0}` + `credit_account`, `debit_account`, `increment_nonce` helpers
- [x] **4.2** Implement genesis block -- `luracoin/genesis.py` with `initialize_chain()`
- [x] **4.3** Optimize database connections -- singleton per database name

## 5. CLI and mining -- DONE

- [x] **5.1** Implement `mine` command -- loop with `Block.create()`
- [x] **5.2** Add CLI commands -- `getBalance`, `getBlock`, `getInfo`

## 6. Mempool -- DONE

- [x] **6.1** Validate transactions before entering mempool
- [x] **6.2** Prioritize transactions by fee (descending), limit to block size
- [x] **6.3** Clean mempool after mining -- `Block.clean_mempool()`

## 7. Networking / P2P -- DEFERRED

- [ ] **7.1** Basic network protocol
- [ ] **7.2** Node discovery
- [ ] **7.3** Block propagation
- [ ] **7.4** Transaction propagation
- [ ] **7.5** Initial Block Download (IBD)

## 8. Tests -- DONE

- [x] **8.1** Fixed all skipped tests (pow, sha256d, block validate, blockchain)
- [x] **8.2** Completed test_full_blockchain
- [x] **8.3** Renamed test_blockchian.py -> test_blockchain.py
- [x] **8.4** Balance validation tests covered in `test_validate_balance_nonce.py`

## 9. Cleanup -- DONE

- [x] **9.1** Deleted `explorer.py`
- [x] **9.2** Deleted `testing.py`
- [x] **9.3** Removed debug prints
- [x] **9.4** Fixed `max_block_size()` -- returns correct value for height

## 10. Deferred (future)

- [ ] **Staking** -- hybrid PoS mechanism
- [ ] **Burn Transactions** -- coin burning
- [ ] **Miners List** -- to be defined
- [ ] **Web Explorer** -- to be decided
- [ ] **Networking / P2P** -- section 7
