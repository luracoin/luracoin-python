# Protocolo Luracoin (alpha)

Esta es una descripción del formato implementado, no una especificación
congelada. P2P v2 y los formatos de consenso pueden cambiar antes de una red
pública. Todos los enteros son sin signo; se indica su endianess en cada campo.

## Redes

| Red | Chain ID | Magic P2P | Génesis |
|---|---:|---|---|
| mainnet | 0 | `ba77d89f` | No definido; el nodo falla cerrado |
| testnet | 1 | `fbc0b6db` | Manifiesto educativo con clave pública conocida |
| devnet | 2 | `faceb00c` | Manifiesto educativo con clave pública conocida |

Una transacción, handshake o mensaje de otra red se rechaza. Los nodos P2P v1
no son compatibles con v2.

## Direcciones y unidades

- Direcciones Base58Check de 34 caracteres.
- Payload de dirección: byte de versión `0x30` + HASH160 de la clave pública
  comprimida.
- 1 LURA = 100.000.000 lurashis.
- Balances y valores se calculan siempre como enteros; no hay coma flotante en
  consenso.

## Transacciones

Una transacción sin firma ocupa 85 bytes. Una transacción completa ocupa
exactamente 213 bytes:

| Offset | Tamaño | Campo | Codificación |
|---:|---:|---|---|
| 0 | 1 | `chain` | Chain ID |
| 1 | 4 | `nonce` | Little-endian |
| 5 | 4 | `fee` | Lurashis, little-endian |
| 9 | 8 | `value` | Lurashis, little-endian |
| 17 | 34 | `from_address` | ASCII |
| 51 | 34 | `to_address` | ASCII |
| 85 | 64 | clave pública | Punto secp256k1 sin prefijo, `x || y` |
| 149 | 64 | firma | Compacta `r || s`, cada entero de 32 bytes |

Para una transacción normal:

1. Se serializan los primeros 85 bytes exactamente como arriba.
2. ECDSA secp256k1 firma esos bytes de forma determinista (RFC 6979) usando
   SHA-256.
3. `s` debe estar en forma low-S (`s <= n/2`).
4. `unlock_sig` es `public_key_x_y || signature_r_s`, 128 bytes.
5. El ID es `SHA256(SHA256(transaction_213_bytes))`, representado como hex.

La dirección derivada de la clave pública debe coincidir con `from_address`.
El nonce válido siguiente es `account.nonce + 1`, y el saldo debe cubrir
`value + fee`. La coinbase usa origen de 34 ceros y un `unlock_sig` de 128
ceros; no es aceptable en el mempool. El destino de 34 ceros también se
rechaza: es un sentinel reservado y esta alpha no define staking ni burn.

El bloque debe contener exactamente una coinbase en la posición cero. Su valor
es el subsidio de la altura más todas las comisiones y su `nonce` es exactamente
la altura del bloque. Así, cada coinbase tiene un ID distinto aunque el minero y
la recompensa coincidan. En altura cero el valor es la asignación del
manifiesto de génesis.

## Bloques

La serialización transmitida y persistida contiene una cabecera de 118 bytes:

| Offset | Tamaño | Campo | Codificación |
|---:|---:|---|---|
| 0 | 4 | `version` | Little-endian; actualmente 1 |
| 4 | 32 | ID declarado | Hash binario del bloque |
| 36 | 32 | `prev_block_hash` | Hash binario |
| 68 | 4 | `height` | Little-endian |
| 72 | 34 | `miner` | Dirección ASCII |
| 106 | 4 | `timestamp` | Big-endian, segundos Unix |
| 110 | 4 | `bits` | Target compacto |
| 114 | 4 | `nonce` | Little-endian |
| 118 | N × 213 | transacciones | Una o más transacciones completas |

El ID no se calcula incluyendo el campo de ID declarado. Su preimagen canónica
es:

```text
version_le_u32
|| prev_block_hash_32
|| height_le_u32
|| miner_ascii_34
|| timestamp_be_u32
|| bits_4
|| nonce_le_u32
|| transaction_count_le_u16
|| concatenated_transactions_213
```

El ID es el doble SHA-256 de esa preimagen. Al deserializar, el nodo vuelve a
calcularlo y rechaza cualquier discrepancia con el ID declarado.

Reglas principales implementadas:

- `prev_block_hash` debe ser el ID del bloque local anterior.
- `bits` debe ser exactamente el target calculado para la altura.
- El ID numérico debe ser menor o igual al target.
- Timestamp estrictamente posterior al bloque previo y no más de 500 segundos
  en el futuro respecto al reloj local.
- Todas las transacciones pertenecen al Chain ID activo, no se repiten y se
  evalúan secuencialmente sobre un snapshot de cuentas.
- El valor recién creado en la coinbase no puede gastarse dentro de ese mismo
  bloque.

El tiempo objetivo es 180 segundos. La dificultad se recalcula cada 480
bloques usando el intervalo real, limitado a un factor de 4 en cada dirección.

El subsidio comienza en 50 LURA y se reduce a la mitad cada 259.200 bloques. Se
aplica un suelo permanente de 1 LURA por bloque, además de las comisiones.

No existe aún selección por trabajo acumulado, almacenamiento de ramas ni
reorganización. Por tanto, estas reglas describen una cadena lineal y no una
finalidad segura bajo competencia entre mineros.

### Índice local de bloques

Cada fichero `blkNNNNNN.dat` concatena registros `length_le_u32 || block`, donde
`length` mide únicamente el bloque serializado. `blocks.db` resuelve una altura
sin recorrer el fichero mediante una entrada versionada de 17 bytes:

| Offset | Tamaño | Campo | Codificación |
|---:|---:|---|---|
| 0 | 1 | versión de ubicación | Actualmente `1` |
| 1 | 4 | número de fichero | Little-endian |
| 5 | 8 | offset del prefijo `length` | Little-endian |
| 13 | 4 | longitud esperada del bloque | Little-endian |

La lectura busca ese offset, exige que el prefijo coincida con la longitud
indexada y lee solo ese bloque. Lecturas y appends usan el mismo lock de
fichero del proceso, separado del lock que serializa la transición de estado,
por lo que una lectura concurrente no interpreta un append en curso como un
registro truncado ni queda bloqueada por la limpieza del mempool.

Los primeros directorios limpios de la alpha v2 guardaban únicamente el número
de fichero en cuatro bytes. Esas entradas se aceptan solo como compatibilidad
interna de v2: se recorre ese fichero una vez y se reemplaza la entrada por la
ubicación versionada. Otros tamaños o versiones fallan cerrados; esto no hace
compatibles los datos del prototipo v1.

Si el proceso termina después de completar un append pero antes de publicar el
índice, el siguiente intento comprueba únicamente las dos posiciones posibles
después del tip (el final de su fichero y el comienzo del siguiente). Esto
recupera el registro sin un recorrido proporcional al historial; un registro
truncado o conflictivo falla cerrado.

## Transporte P2P v2

Cada mensaje TCP tiene una cabecera de 24 bytes seguida del payload:

| Offset | Tamaño | Campo |
|---:|---:|---|
| 0 | 4 | Magic de la red |
| 4 | 12 | Comando ASCII, relleno derecho con ceros |
| 16 | 4 | Longitud del payload, little-endian |
| 20 | 4 | Primeros 4 bytes de doble SHA-256 del payload |

El lector valida comando y longitud antes de reservar/leer el payload. El
máximo global es 8.000.004 bytes y un bloque no puede superar 8.000.000 bytes.

### Handshake

`VERSION` tiene 18 bytes:

| Tamaño | Campo | Codificación |
|---:|---|---|
| 4 | `protocol_version` | Little-endian; debe ser 2 |
| 4 | `chain_id` | Little-endian; debe coincidir con la red local |
| 4 | `height` | Little-endian |
| 4 | `timestamp` | Little-endian |
| 2 | `listening_port` | Little-endian, no cero |

Ambos lados intercambian `VERSION` y `VERACK` antes de activar el peer. Un
`VERSION`/`VERACK` posterior al handshake es error de protocolo.

### Comandos

| Comando | Payload |
|---|---|
| `version` | 18 bytes, descritos arriba |
| `verack` | Vacío |
| `getpeers` | Vacío |
| `peers` | `count` u16 LE + hasta 256 pares IPv4(4) + puerto u16 LE |
| `getblocks` | altura inicial u32 LE + cantidad u16 LE |
| `block` | 118 + N × 213 bytes |
| `tx` | Una transacción de 213 bytes |
| `inv` | tipo u8 (`1` bloque, `2` tx) + hash de 32 bytes |
| `getdata` | Mismo formato que `inv` |
| `ping` | Nonce u64 LE |
| `pong` | Nonce u64 LE correspondiente |

La sincronización solicita como máximo 50 bloques por lote y aplica únicamente
alturas consecutivas. El nodo limita peers totales e inbound a 8 por defecto y
acota sus cachés de inventario. Una dirección que falla durante el sync queda
excluida de reconexión y selección mediante cooldown exponencial en memoria: 30
segundos inicialmente, hasta 900 segundos por defecto. Una sincronización
correcta reinicia su historial de fallos.

Los envíos a peers son concurrentes y tienen timeout. El replay de transacciones
pendientes conserva como máximo 1.000 elementos y, por peer y ciclo, procesa un
máximo de 100 durante un presupuesto total de 5 segundos. Un fallo inesperado
no descarta los conteos parciales exitosos y provoca la retirada del peer
fallido. `LURACOIN_SYNC_COOLDOWN_BASE`, `LURACOIN_SYNC_COOLDOWN_MAX`,
`LURACOIN_SYNC_COOLDOWN_LIMIT`, `LURACOIN_PENDING_RELAY_LIMIT`,
`LURACOIN_REPLAY_BATCH_SIZE` y `LURACOIN_REPLAY_BUDGET_SECONDS` permiten ajustar
estos límites. El cooldown identifica el host/IP normalizado, no el puerto
anunciado, y conserva como máximo 4.096 historiales por defecto. Estas defensas
no sustituyen rate limiting, peer scoring persistente, protección Sybil ni sync
por headers.

## RPC local v1

El RPC es HTTP sobre loopback, no forma parte del protocolo P2P ni debe
exponerse a Internet. Usa bearer token persistido como `rpc.token` con permisos
`0600`.

| Método y ruta | Autenticación | Resultado |
|---|---|---|
| `GET /health` | No | Salud mínima, red y versión API |
| `GET /v1/status` | Sí | Red, altura local/conocida, peers, `syncing` y `ready` |
| `GET /v1/accounts/{address}` | Sí | Balance confirmado/gastable, nonce y estado del mempool |
| `GET /v1/accounts/{address}/transactions` | Sí | Pendientes + historial indexado, `limit` 1–200 y cursor opaco |
| `GET /v1/blocks/{height}` | Sí | Bloque y transacciones |
| `POST /v1/transactions` | Sí | Admite y propaga 213 bytes en hex |

El POST recibe `{"raw":"..."}`; el hex debe medir 426 caracteres. Una
respuesta `202` indica que el nodo la admitió en su mempool, no que esté minada
ni sea final. `relay_count` informa cuántos peers recibieron la escritura
inicial y `broadcast` equivale a `relay_count > 0`; una aceptación con cero
peers sigue siendo local y queda en el backlog acotado de relay. Mientras
`ready` sea falso, el POST responde `503 node_not_ready`.

En las respuestas JSON, `balance`, `spendable_balance`, `value` y `fee` son
cadenas decimales. `nonce` refleja la cadena confirmada y `next_nonce` incorpora
la secuencia contigua de salidas pendientes que el nodo pudo leer de Redis. Si
Redis no está disponible, `mempool_available` es falso y el cliente no debe
habilitar un envío.

Al confirmar una transacción, una candidata pendiente con el mismo
`chain + sender + nonce` deja de ser válida aunque tenga otro ID. El nodo
captura esa candidata antes de aplicar el bloque y elimina después tanto la
reserva como su payload Redis mediante comparaciones atómicas del ID y los bytes
esperados, sin borrar una escritura concurrente distinta.

El historial confirmado se resuelve mediante un índice por dirección. Las
transacciones pendientes solo se incluyen cuando no se envía `cursor`; una
respuesta con `next_cursor` puede pasarse sin interpretar en la consulta
siguiente.

## Gateway local de wallet web

Al proporcionar `--wallet-dir`, `node` o `mine` sirve esa build Vite/SPA y un
gateway HTTP separado. El RPC v1 permanece enlazado exclusivamente a loopback y
con bearer obligatorio; el gateway añade ese bearer en servidor y nunca lo
incluye en HTML, JavaScript, cookies, respuestas o cabeceras hacia el navegador.
La raíz estática debe ser un `dist` dedicado: no puede contener el directorio de
datos privado y cualquier fichero llamado `rpc.token` queda bloqueado. No es un
proxy RPC genérico. Su allowlist completa es:

| Método y ruta web | Ruta RPC privada |
|---|---|
| `GET /wallet-api/status` | `GET /v1/status` |
| `GET /wallet-api/accounts/{address}` | `GET /v1/accounts/{address}` |
| `GET /wallet-api/accounts/{address}/transactions` | La misma ruta `/v1`, solo con `limit` y `cursor` |
| `POST /wallet-api/transactions` | `POST /v1/transactions` |

`GET /wallet-health` comprueba únicamente el proceso web y no requiere cookie.
Las demás rutas `/wallet-api/*`, las rutas `/v1/*` directas, queries no
permitidas, redirects y respuestas que no sean JSON se rechazan.

La primera respuesta SPA instala una cookie aleatoria por proceso con
`HttpOnly`, `SameSite=Strict`, path `/` y sin contenido del bearer. Cada acceso
al gateway exige esa cookie y `Sec-Fetch-Site: same-origin`; los POST exigen
además un `Origin` idéntico. Toda petición valida un `Host` local exacto
(`localhost` o `127.0.0.1`) para mitigar DNS rebinding. No se emiten cabeceras
CORS y las cabeceras upstream, incluido `Set-Cookie`, no se propagan.

El cuerpo web se limita a 16 KiB, la respuesta RPC descomprimida a 2.000.000
bytes, cada fichero estático a 16 MiB y el salto RPC a 5 segundos. El bind web
predeterminado es `127.0.0.1:8080`. `--wallet-host 0.0.0.0` solo habilita el bind
dentro de un contenedor: el puerto debe publicarse como
`127.0.0.1:8080:8080`, nunca sobre todas las interfaces del host. Esta opción no
cambia ni amplía el bind privado del RPC.

## Compatibilidad

Los vectores de [`vectors.json`](../vectors.json) son la referencia ejecutable
para interoperabilidad Python/JavaScript. Antes de cambiar cualquier byte,
algoritmo de firma o regla de hash deben actualizarse de forma deliberada:

1. la versión del protocolo/consenso;
2. los vectores y pruebas negativas;
3. nodo, wallet y cualquier implementación independiente;
4. el plan coordinado de migración de datos y peers.
