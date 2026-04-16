# Luracoin - Roadmap to Complete Blockchain

## Esencial

- [ ] **1. Integrar P2P con el miner** -- Al minar, broadcast a peers. Al recibir bloque, parar mining y empezar siguiente. Recibir TXs de peers al mempool.
- [ ] **2. Ajuste de dificultad integrado** -- Llamar a `calculate_new_bits()` cada `DIFFICULTY_ADJUSTMENT_INTERVAL` bloques en vez de usar siempre `STARTING_DIFFICULTY`.
- [ ] **3. Validar prev_block_hash** -- `Block.validate()` debe comprobar que `prev_block_hash` sea el hash real del bloque anterior.
- [ ] **4. Longest chain rule** -- Seleccionar la cadena más larga cuando hay forks. Dos miners con bloque simultáneo → elegir la cadena con más trabajo acumulado.

## Importante

- [ ] **5. Merkle tree** -- Merkle root en el header del bloque para verificación eficiente de transacciones.
- [ ] **6. HTTP API / RPC** -- API JSON-RPC para que wallets y apps interactúen con el nodo.
- [ ] **7. Chain reorganization** -- Rollback de transacciones y re-aplicar cuando llega una cadena más larga.

## Cosmético

- [ ] **8. Persistir peers en disco** -- Guardar peers conocidos para no depender solo de seed nodes al reiniciar.
- [ ] **9. Compact block propagation** -- Enviar solo headers + short tx IDs en vez de bloques completos.
