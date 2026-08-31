# Luracoin Python

Implementación de referencia en Python de Luracoin, una blockchain educativa
Proof of Work con modelo de cuentas.

> **Estado: alpha para desarrollo y testnet.** No existe una mainnet pública,
> estos activos no tienen valor real y el código no ha recibido una auditoría
> de seguridad independiente. No uses Luracoin para custodiar valor.

## Estado actual

| Área | Estado |
|---|---|
| Consenso lineal, PoW y estado de cuentas | Implementado y cubierto por tests |
| Testnet y devnet locales | Disponibles; su génesis usa una clave públicamente conocida |
| Mainnet | Bloqueada de forma intencional: no hay manifiesto de génesis |
| Protocolo P2P | Versión 2, incompatible con la versión 1 |
| Sincronización | Descarga secuencial de la cadena canónica |
| RPC para wallet | HTTP local autenticado, API v1 |
| API de explorer | FastAPI read-only; índice SQLite analítico opcional |
| Mempool | Redis, con reserva atómica de `sender + nonce` |
| Fork choice y reorganizaciones | **No implementados** |
| Seeds públicos e infraestructura de testnet | **No desplegados** |

El nodo solo acepta el siguiente bloque de su cadena local. Valida el hash del
bloque anterior, la dificultad esperada, una única coinbase, la recompensa y
las transiciones de cuenta en orden. Todavía no puede comparar ramas ni
reorganizarse si dos mineros producen bloques competidores.

## Parámetros relevantes

- Modelo de cuentas: cada dirección mantiene `balance` y `nonce`.
- Unidad mínima: 1 LURA = 100.000.000 lurashis.
- Tiempo objetivo de bloque: 180 segundos.
- Recompensa inicial: 50 LURA, más las comisiones del bloque.
- Halving cada 259.200 bloques.
- Emisión de cola: la recompensa nunca baja de 1 LURA por bloque.
- Transacción firmada: exactamente 213 bytes.
- Bloque: cabecera serializada de 118 bytes más transacciones.
- Puerto P2P predeterminado: TCP 9999.

La especificación binaria actual está en
[`docs/PROTOCOL.md`](https://github.com/luracoin/luracoin-python/blob/master/docs/PROTOCOL.md).
Cambiar una codificación, un hash o una
regla de validación puede romper el consenso y requiere nuevos vectores de
interoperabilidad.

## Requisitos

- Python 3.10–3.12.
- Redis 7 recomendado. Redis almacena el mempool y debe estar disponible para
  admitir, propagar o minar transacciones pendientes.
- Una plataforma compatible con `rocksdict`.
- `uv` para reproducir el entorno bloqueado y los controles de CI/release.

En macOS, Redis puede instalarse con Homebrew:

```sh
brew install redis
brew services start redis
```

En Ubuntu/Debian:

```sh
sudo apt update
sudo apt install -y python3 python3-venv redis-server
sudo systemctl enable --now redis-server
```

## Instalación

```sh
git clone https://github.com/luracoin/luracoin-python.git
cd luracoin-python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Comprueba la instalación y Redis:

```sh
redis-cli ping
pytest -q
luracoin --help
```

## Redes y datos

La red predeterminada es `testnet`. Cada red tiene un `chain_id`, bytes
mágicos P2P, base Redis y directorio de datos independientes:

| Red | `chain_id` | Magic P2P | RPC predeterminado | Utilidad |
|---|---:|---|---:|---|
| `testnet` | 1 | `fbc0b6db` | 18444 | Integración local y entre desarrolladores |
| `devnet` | 2 | `faceb00c` | 28444 | Tests y redes desechables |
| `mainnet` | 0 | `ba77d89f` | 8444 | Reservada; no puede inicializarse aún |

Sin opciones, los datos se guardan en `~/.luracoin/<network>`. Puedes cambiar
la raíz con `LURACOIN_HOME` o usar un directorio exacto con `--data-dir`. No
reutilices un mismo directorio entre redes.

Consulta
[`.env.example`](https://github.com/luracoin/luracoin-python/blob/master/.env.example)
para la configuración por entorno.
Es una plantilla: el CLI no carga `.env` automáticamente, por lo que las
variables deben exportarse en la shell antes de iniciar el proceso.

## CLI

Los nombres con guiones son la interfaz canónica. Los nombres camelCase
antiguos se conservan como aliases de compatibilidad.

```sh
# Imprimir una wallet una sola vez (contiene secretos; no la publiques)
luracoin generate-wallet --network testnet

# Nodo P2P + RPC local autenticado
luracoin node --network testnet --port 9999 --rpc-port 18444

# Crear y poblar también el índice histórico/analítico (opt-in)
luracoin node --network testnet --explorer-index

# Full node + wallet web en un solo proceso (tras compilar el Vite dist)
luracoin node --network testnet --port 9999 --rpc-port 18444 \
  --wallet-dir ../luracoin-wallet/dist

# Nodo P2P + RPC + minería
luracoin mine --network testnet --address <DIRECCION> \
  --port 9999 --rpc-port 18444

# Consultas locales
luracoin get-info --network testnet
luracoin get-balance --network testnet <DIRECCION>
luracoin get-block --network testnet <ALTURA>
```

Todos los subcomandos aceptan `--network` y `--data-dir`. `node` y `mine`
también aceptan `--rpc-host`, pero el servidor rechaza direcciones que no sean
loopback (`127.0.0.1`, `::1` o `localhost`). Seleccionar `mainnet` no la activa:
los comandos que inicializan cadena terminan con error hasta que exista un
génesis nuevo y auditado.

No hay seeds públicos configurados. Para una prueba entre nodos, repite
`--seed HOST:PORT` en `node` o `mine` con las direcciones controladas que deban
usarse. `--host` configura el bind P2P; no afecta al bind loopback del RPC.

### Wallet web opcional

`node` y `mine` pueden servir una build Vite/SPA con `--wallet-dir`. El bind
predeterminado es `127.0.0.1:8080`; abre `http://127.0.0.1:8080/` o
`http://localhost:8080/`. `--wallet-port` cambia ese puerto. El navegador nunca
lee `rpc.token`: habla con cuatro rutas `/wallet-api/*` explícitas y el proceso
Python añade el bearer únicamente al salto privado hacia el RPC loopback.
Usa un directorio `dist` dedicado: el servidor rechaza una raíz que contenga
el directorio privado de datos del nodo y nunca sirve un fichero `rpc.token`.

El gateway usa una cookie aleatoria por proceso, `HttpOnly` y `SameSite=Strict`;
valida `Host`, `Origin` y `Sec-Fetch-Site`, no habilita CORS, rechaza redirects y
acota cuerpos, respuestas, ficheros estáticos y tiempo de espera. Solo expone:

- `GET /wallet-api/status`
- `GET /wallet-api/accounts/{address}`
- `GET /wallet-api/accounts/{address}/transactions?limit=50&cursor=<opaco>`
- `POST /wallet-api/transactions` con `{"raw":"<426 caracteres hex>"}`
- `GET /wallet-health` para salud del servidor web

`--wallet-host 0.0.0.0` existe exclusivamente para que un contenedor escuche en
su namespace. Publica siempre el puerto en loopback del host, por ejemplo
`127.0.0.1:8080:8080`; nunca uses `8080:8080`, `0.0.0.0:8080:8080` ni un proxy
público. El RPC conserva su bind loopback obligatorio incluso en Docker y su
puerto no debe publicarse.

## API de block explorer

`node` y `mine` arrancan también una API FastAPI read-only en loopback. No usa
ni expone el bearer del RPC y no contiene rutas de escritura. Los puertos
predeterminados son `8000` para mainnet, `18000` para testnet y `28000` para
devnet. La documentación interactiva está en `/docs` y el contrato OpenAPI en
`/openapi.json`.

La guía operativa completa, con configuración, endpoints, estados del
backfill, almacenamiento y recomendaciones para exposición pública, está en
[`docs/EXPLORER_API.md`](docs/EXPLORER_API.md).

Estas rutas funcionan en cualquier full node sin crear una base adicional:

- `GET /health`
- `GET /api/v1/status`
- `GET /api/v1/features`
- `GET /api/v1/blocks?limit=10&before_height=<altura>`
- `GET /api/v1/blocks/{altura-o-hash}`
- `GET /api/v1/blocks/{altura-o-hash}/transactions`
- `GET /api/v1/transactions/{txid}`
- `GET /api/v1/addresses/{direccion}`

Las consultas que necesitan recorrer o agregar toda la historia están
publicadas en el mismo OpenAPI, pero requieren el índice opcional:

- `GET /api/v1/transactions`
- `GET /api/v1/addresses`
- `GET /api/v1/addresses/{direccion}/transactions`
- `GET /api/v1/stats`

Actívalo explícitamente con `--explorer-index` o
`LURACOIN_EXPLORER_INDEX=true`. En el primer arranque se crea
`<data-dir>/explorer.sqlite3`, se popula en segundo plano desde los bloques
existentes y después sigue la punta de forma incremental. `/api/v1/status`
publica su progreso. Mientras está desactivado o construyéndose, las rutas que
dependen de él responden `503` con un error y estado estables; las rutas básicas
siguen disponibles. Sin ese opt-in no se crea ni se abre ningún fichero
SQLite.

Usa `--no-explorer-api` para desactivar incluso la API ligera,
`--explorer-host`/`--api-host` y `--explorer-port`/`--api-port` para el bind, y
`--explorer-db` para una ruta SQLite distinta. Exponerla mediante `0.0.0.0` es
una decisión explícita: colócala detrás de un reverse proxy con TLS, límites de
peticiones y cuotas de respuesta.

`--explorer-index` requiere que la API permanezca habilitada; combinarlo con
`--no-explorer-api` se rechaza explícitamente. La lista básica carga los bloques
de uno en uno y limita cada página a diez para acotar el uso de memoria incluso
cuando haya bloques cercanos al tamaño máximo del protocolo. El detalle de un
bloque devuelve su resumen; sus transacciones se obtienen por la subruta
paginada `/api/v1/blocks/{altura-o-hash}/transactions`.

Los importes se devuelven como strings decimales para conservar `uint64`. Una
"confirmación" solo expresa profundidad observada: todavía no es finalidad,
porque Luracoin aún no implementa fork choice ni reorganizaciones.

## RPC local

`node` y `mine` exponen una API HTTP solo en loopback. En el primer arranque se
crea `rpc.token` dentro del directorio de datos con permisos `0600`. Todas las
rutas `/v1/*` requieren `Authorization: Bearer <token>`; únicamente `/health`
es pública.

Rutas disponibles:

- `GET /health`
- `GET /v1/status`
- `GET /v1/accounts/{address}`
- `GET /v1/accounts/{address}/transactions?limit=50&cursor=<opaco>`
- `GET /v1/blocks/{height}`
- `POST /v1/transactions` con `{"raw":"<426 caracteres hex>"}`

Los importes de la API se devuelven como cadenas decimales para no perder
precisión en JavaScript. La cuenta distingue balance confirmado, balance
gastable tras salidas pendientes, nonce confirmado y `next_nonce`; el historial
incluye salidas pendientes y transacciones confirmadas. Los ingresos aún no se
indexan desde el mempool y aparecen al confirmarse. El token no debe copiarse
al renderer, incluirse en un repositorio ni exponerse en una URL remota.
El wallet web opcional no relaja esta frontera: su gateway es una allowlist, no
un proxy general, y nunca devuelve el bearer al navegador.

`status` publica `height`, `best_peer_height`, `syncing` y `ready`. Un envío se
rechaza con `503 node_not_ready` mientras el nodo conoce una altura superior a
la local. El historial usa un índice por dirección; las pendientes solo
aparecen en la primera página y `next_cursor` permite continuar con las
confirmadas. En el recibo de un envío, `accepted` significa admisión local,
`relay_count` cuenta peers escritos con éxito y `broadcast` solo es verdadero
cuando ese conteo es mayor que cero.

Las transacciones aceptadas quedan en un backlog local acotado y se reintentan
sin monopolizar el ciclo de red: por defecto se conservan 1.000, y cada peer
recibe como máximo 100 por ciclo durante un presupuesto total de 5 segundos.
Una dirección que falla durante la sincronización entra en cooldown exponencial
de 30 a 900 segundos y no se reconecta ni se elige como candidata durante ese
intervalo. Estos límites pueden ajustarse con las variables documentadas en
`.env.example`.

## Almacenamiento

La cadena usa tres bases RocksDB (`rocksdict`) para cuentas, índices y
chainstate. Los bloques se escriben como registros con longitud en ficheros
`blocks/blkNNNN.dat`, rotados alrededor de 128 MiB. Cada altura indexa fichero,
offset y longitud para leer un único registro; las entradas v2 antiguas que solo
indicaban fichero se actualizan perezosamente. La aplicación de cuentas se hace
por lotes y los reintentos del mismo bloque son idempotentes, pero esto no
equivale a disponer de rollback o recuperación completa ante cualquier fallo.

Redis contiene únicamente el mempool; no es la fuente de verdad de la cadena.
Las bases Redis predeterminadas son distintas para mainnet, testnet y devnet.
Al confirmar una transacción, el nodo elimina también cualquier candidata local
que compita por el mismo `sender + nonce`; la reserva y el payload Redis se
borran de forma condicionada para no eliminar una escritura concurrente.

Cuando se activa, `explorer.sqlite3` es una proyección derivada y reemplazable:
normaliza cabeceras, transacciones, actividad por dirección y agregados, pero
no duplica bloques raw ni material privado. Usa WAL y checkpoints
transaccionales para reanudar el backfill. Una base configurada para otra red
se rechaza; si la cadena derivada de la misma red fue reiniciada, el índice se
reconstruye desde la fuente canónica.

RocksDB conserva además el índice canónico compacto de localización de
transacciones y el historial que ya consume el RPC de wallet. Esta primera
versión no lo migra: el opt-in evita exclusivamente la proyección SQLite
desnormalizada. Convertir también ese historial de compatibilidad en opcional
requiere versionar el contrato del RPC y su migración de datos.

## Desarrollo y verificación

```sh
uv lock --check
uv sync --frozen --extra dev
uv run pytest -q
uv run coverage run --source=luracoin -m pytest -q
uv run coverage report --fail-under=80
uv build --clear --python python
uv run twine check --strict dist/*
```

Antes de publicar una red o binario, sigue la
[`docs/RELEASE_CHECKLIST.md`](https://github.com/luracoin/luracoin-python/blob/master/docs/RELEASE_CHECKLIST.md).
Los pendientes priorizados están en
[`TODO.md`](https://github.com/luracoin/luracoin-python/blob/master/TODO.md) y
[`docs/TODO-blockchain.md`](https://github.com/luracoin/luracoin-python/blob/master/docs/TODO-blockchain.md).
Los cambios incompatibles y el uso de un directorio nuevo se explican en el
[`CHANGELOG.md`](https://github.com/luracoin/luracoin-python/blob/master/CHANGELOG.md)
y la
[`docs/MIGRATION.md`](https://github.com/luracoin/luracoin-python/blob/master/docs/MIGRATION.md).

## Seguridad

- El génesis de testnet/devnet deriva de material que fue publicado. Es
  deliberadamente inseguro y solo sirve para redes sin valor.
- `generate-wallet` produce secretos. Trátalos como credenciales y no uses sus
  valores como ejemplos en documentación o incidencias.
- No hay finalización fiable ante forks mientras falten selección por trabajo
  acumulado y reorganizaciones.
- El protocolo, la criptografía, el almacenamiento y el proceso de release
  necesitan auditoría independiente antes de considerar una mainnet.

Consulta la
[`SECURITY.md`](https://github.com/luracoin/luracoin-python/blob/master/SECURITY.md)
para reportar vulnerabilidades de forma privada.
