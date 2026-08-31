# Luracoin — estado y trabajo pendiente

Este documento separa lo que ya está implementado de lo que impide una red
pública. Una casilla marcada significa que existe código y cobertura, no que
la funcionalidad haya sido auditada para producción.

## Endurecimiento completado para alpha

- [x] Validación contextual de balances y nonces dentro de un bloque.
- [x] Una única coinbase como primera transacción; recompensa igual a subsidio
  más comisiones, sin doble crédito al minero.
- [x] Validación de `prev_block_hash` y dificultad esperada.
- [x] Halvings enteros cada 259.200 bloques y emisión de cola de 1 LURA.
- [x] Hashes canónicos binarios para transacción y bloque.
- [x] Firma determinista ECDSA/secp256k1 con SHA-256 y forma compacta low-S.
- [x] Transacciones firmadas de 213 bytes y vectores Python/JavaScript.
- [x] Escritura de estado por lotes, guardado idempotente y rotación de
  ficheros de bloques.
- [x] Entropía de wallet obtenida del CSPRNG del sistema.
- [x] Configuración aislada de `testnet`, `devnet` y `mainnet`; testnet por
  defecto.
- [x] Mainnet bloqueada cuando no existe un manifiesto de génesis auditado.
- [x] P2P v2 con identificación de cadena, límites de payload, un lector por
  peer, ping/pong, discovery básico, relay y apagado limpio.
- [x] Sincronización secuencial de la cadena lineal.
- [x] Cooldown exponencial temporal tras fallos de sync y relay/replay acotado
  por timeout, lote y presupuesto total, preservando éxitos parciales.
- [x] Mempool Redis con reserva atómica de `sender + nonce` y limpieza segura de
  reserva y payload de candidatas competidoras al confirmar.
- [x] RPC HTTP v1 autenticado y limitado a loopback.
- [x] Full node de un comando con SPA opcional y gateway wallet de allowlist,
  cookie HttpOnly y bearer conservado exclusivamente en servidor.
- [x] CI con Redis, varias versiones de Python, cobertura y build del paquete.

## Bloqueantes de una testnet pública

- [ ] Implementar selección de cadena por **trabajo acumulado**, no por altura
  declarada ni por orden de llegada.
- [ ] Implementar forks, almacenamiento de ramas laterales y reorganizaciones
  atómicas con undo data para cuentas, nonces y transacciones.
- [ ] Añadir sincronización por headers/checkpoints y resistencia a peers que
  anuncien alturas o cadenas maliciosas.
- [ ] Persistir y puntuar peers; convertir el cooldown actual en estado durable
  y añadir bans temporales y protección Sybil básica.
- [ ] Desplegar al menos dos seeds independientes y documentar su operación,
  monitorización y actualización coordinada a P2P v2.
- [ ] Ejecutar pruebas multi-nodo prolongadas: particiones, bloques simultáneos,
  reinicios durante commits, corrupción y recuperación de disco.
- [ ] Diseñar migraciones de datos y de protocolo antes de cambiar formatos de
  consenso.
- [ ] Añadir observabilidad operativa: logs estructurados, métricas, límites de
  disco y alertas.
- [ ] Publicar faucet y explorer específicos de testnet, sin mezclar datos de
  demostración con datos de red.
- [ ] Someter consenso, P2P, RPC, wallet y cadena de suministro a revisión
  independiente.

## Bloqueantes adicionales de mainnet

- [ ] Congelar una especificación versionada y un proceso de upgrades de
  consenso.
- [ ] Realizar una ceremonia de génesis nueva. La clave histórica de desarrollo
  es pública y no puede reutilizarse.
- [ ] Definir y revisar distribución inicial, custodia, transparencia y
  gobernanza de cambios.
- [ ] Obtener al menos una implementación o verificador independiente que use
  los mismos vectores de consenso.
- [ ] Hacer reproducibles y firmados los artefactos de release y verificar
  dependencias/SBOM.
- [ ] Completar threat model, auditoría externa y programa privado de reporte.
- [ ] Ejecutar una testnet pública estable durante un periodo acordado y cerrar
  todos los incidentes críticos antes de fijar fecha de lanzamiento.

## Mejoras posteriores

- [x] Índice por hash de bloque e historial paginado por dirección, sin
  recorrer toda la cadena en cada consulta RPC.
- [ ] Propagación compacta de bloques e inventarios agrupados.
- [ ] Políticas de reemplazo de transacciones explícitas; no prometer RBF hasta
  que consenso y mempool lo definan.
- [ ] Snapshots verificables y herramientas de reparación/exportación.
- [ ] Hardware wallets, multi-dirección/HD, watch-only y multisig.
- [ ] Explorer web y herramientas de operación remota separadas del RPC local.
- [ ] Staking, burn u otros cambios económicos solo mediante una propuesta de
  consenso nueva; actualmente no forman parte del protocolo.

La lista técnica detallada se mantiene en
[`docs/TODO-blockchain.md`](docs/TODO-blockchain.md).
