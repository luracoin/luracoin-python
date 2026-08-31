# Roadmap técnico de blockchain

Estado objetivo inmediato: una testnet pública recuperable y observable. La
implementación actual es una alpha lineal; no es una mainnet ni garantiza
finalidad cuando aparece un fork.

## P0 — Consenso y recuperación

- [ ] **Árbol de bloques.** Indexar por hash y almacenar bloques válidos que no
  extiendan el tip actual, en lugar de descartarlos por altura.
- [ ] **Trabajo acumulado.** Calcular chainwork a partir del target de cada
  bloque y seleccionar la rama válida con mayor trabajo acumulado.
- [ ] **Reorganización atómica.** Persistir undo data por bloque, desconectar la
  rama antigua y conectar la nueva sin dejar balances, nonces, índices o
  mempool a medias.
- [ ] **Recuperación de crash.** Añadir journal/commit marker que cubra de forma
  conjunta fichero de bloques, cuentas e índices; probar fallos inyectados en
  cada frontera de escritura.
- [ ] **Timestamps.** Definir median-time-past y reglas deterministas más fuertes
  que la comparación estricta con el bloque anterior.
- [ ] **Dificultad.** Revisar matemáticamente la codificación compacta, límites,
  overflow y comportamiento alrededor de reorganizaciones y checkpoints.
- [ ] **Conformance suite.** Ampliar vectores negativos y positivos para hashes,
  firmas low-S, targets, génesis, recompensas y transiciones multi-cuenta.

## P0 — Seguridad de red

- [ ] Sincronizar headers antes que bloques y verificar chainwork antes de
  descargar cuerpos grandes.
- [ ] Evitar que una altura remota no verificada dirija el proceso de IBD.
- [x] Acotar escrituras y replay por timeout, lote y presupuesto total; aplicar
  cooldown exponencial en memoria a direcciones que fallen durante el sync.
- [ ] Añadir puntuación de mal comportamiento, rate limits por comando/IP y
  persistencia del cooldown y los bans temporales.
- [ ] Evitar eclipses: diversidad de subred/ASN, múltiples seeds y selección
  aleatoria de peers salientes.
- [ ] Añadir límites explícitos de ancho de banda, colas y trabajo de validación,
  además del límite actual de bytes.
- [ ] Definir compatibilidad/upgrades del protocolo; P2P v2 es incompatible con
  nodos v1 y exige actualización coordinada.
- [ ] Fuzzear framing, parsers, handshake, bloques y transacciones.

## P1 — Mempool y propagación

- [ ] Definir política de expiración, tamaño total y desalojo del mempool.
- [ ] Definir reemplazo por fee de manera explícita. Hoy una reserva
  `sender + nonce` evita dos candidatas simultáneas; no existe RBF estable.
- [x] Eliminar de forma atómica la reserva y el payload huérfano de una
  candidata `sender + nonce` competidora cuando otra se confirma.
- [ ] Reinsertar transacciones desconectadas durante una reorganización.
- [ ] Persistir o reconstruir el mempool de forma segura al reiniciar.
- [ ] Usar inventarios agrupados y propagación compacta de bloques.
- [ ] Separar fallos transitorios de Redis de rechazos permanentes y exponerlos
  con métricas.

## P1 — Almacenamiento e índices

- [x] Índices directos `block_hash -> altura`, `altura -> fichero/offset/longitud`
  e historial por dirección sin recorrer todos los bloques.
- [ ] Herramientas `verify`, `reindex`, backup y restore con comprobación de
  hashes.
- [ ] Cuotas y avisos de disco; manejo probado de disco lleno y ficheros
  truncados.
- [ ] Versión de esquema y migraciones reproducibles para RocksDB y ficheros
  `blk`.
- [ ] Tras versionar el RPC de wallet, hacer opcional o migrar su índice
  compacto de historial por dirección para que un full node mínimo no lo
  duplique junto al índice SQLite del explorer.
- [ ] Bloqueo de proceso para impedir dos nodos sobre el mismo `data-dir`.

## P1 — RPC y operación

- [ ] Versionar formalmente request/response y códigos de error de RPC v1.
- [x] Añadir paginación por cursor e índices por dirección para historial.
- [ ] Aplicar rate limits incluso en loopback y registrar fallos sin filtrar el
  bearer token ni material de wallet.
- [x] Servir opcionalmente el wallet Vite con gateway de rutas limitado,
  controles de Host/Origin/Fetch Metadata y bearer solo en servidor.
- [ ] Estado de salud detallado para Redis, almacenamiento, P2P y sincronía.
- [ ] Shutdown por señales, logs estructurados y métricas.
- [x] Separar con claridad el RPC local autenticado del servicio público y
  read-only de explorer. No exponer el token local por red.

## P1 — Infraestructura de testnet

- [ ] Dos o más seeds operados por entidades/hosts distintos.
- [ ] Faucet con rate limits y sin reutilizar material de clave comprometido.
- [x] API de explorer que marque de forma inequívoca testnet/devnet; la UI y
  su despliegue público siguen pendientes.
- [ ] Pruebas de caos y soak multi-nodo con bloques competidores y particiones.
- [ ] Runbooks para despliegue, rollback binario, incidentes y reset coordinado
  de una testnet educativa.

## P0 antes de mainnet

- [ ] Nueva ceremonia y manifiesto de génesis auditado; el código debe continuar
  fallando cerrado mientras falte.
- [ ] Especificación de consenso congelada y revisada por terceros.
- [ ] Implementación/verificador independiente y vectores compartidos.
- [ ] Auditoría externa de consenso, criptografía, P2P, RPC, wallet, builds y
  dependencias.
- [ ] Releases reproducibles, firmadas, con SBOM y procedimiento de divulgación
  de vulnerabilidades.
- [ ] Criterios públicos de estabilidad de testnet y respuesta a incidentes.

## Fuera del alcance actual

Merkle proofs, staking, burn, multisig, contratos y consenso híbrido no están
implementados. Cada uno altera superficie de ataque o reglas económicas y no
debe incorporarse como mejora cosmética.
