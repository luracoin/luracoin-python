# API de block explorer

Luracoin incluye una API HTTP pública y de solo lectura pensada para construir
block explorers, paneles de estado y herramientas de consulta. La API se
ejecuta con FastAPI dentro de los comandos `node` y `mine`, pero está separada
del RPC privado de la wallet: no usa ni expone `rpc.token` y no contiene rutas
de escritura.

La funcionalidad está dividida deliberadamente en dos niveles:

- **API core:** está habilitada por defecto, consulta los almacenes canónicos
  del full node y no crea una base de datos adicional.
- **Índice de explorer:** es una proyección SQLite desnormalizada, opcional y
  reconstruible. Añade consultas históricas, rankings y agregados que serían
  demasiado costosos para todos los full nodes.

## Inicio rápido

Un nodo de testnet arranca la API core en loopback automáticamente:

```sh
luracoin node --network testnet
```

Sus interfaces de consulta son:

- Swagger UI: `http://127.0.0.1:18000/docs`
- ReDoc: `http://127.0.0.1:18000/redoc`
- OpenAPI JSON: `http://127.0.0.1:18000/openapi.json`
- Estado: `http://127.0.0.1:18000/api/v1/status`

Los puertos predeterminados dependen de la red:

| Red | Puerto del explorer |
|---|---:|
| mainnet | 8000 |
| testnet | 18000 |
| devnet | 28000 |

Mainnet continúa bloqueada hasta que exista un génesis público y auditado; el
puerto se reserva para mantener una configuración consistente entre redes.

Para crear y poblar el índice histórico:

```sh
luracoin node --network testnet --explorer-index
```

La primera ejecución crea `<data-dir>/explorer.sqlite3`, indexa en segundo
plano los bloques existentes y después sigue la punta de la cadena. Las rutas
core continúan disponibles durante todo el backfill.

## Configuración

`node` y `mine` aceptan las mismas opciones:

| Opción CLI | Variable de entorno | Valor predeterminado | Efecto |
|---|---|---|---|
| `--explorer-api` / `--no-explorer-api` | `LURACOIN_EXPLORER_API` | `true` | Activa o desactiva toda la API. |
| `--explorer-host`, `--api-host` | `LURACOIN_EXPLORER_HOST` | `127.0.0.1` | Dirección de escucha. |
| `--explorer-port`, `--api-port` | `LURACOIN_EXPLORER_PORT` | Según la red | Puerto de escucha. |
| `--explorer-index` / `--no-explorer-index` | `LURACOIN_EXPLORER_INDEX` | `false` | Crea, rellena y sigue el índice SQLite. |
| `--explorer-db` | `LURACOIN_EXPLORER_DB` | `<data-dir>/explorer.sqlite3` | Ruta de la proyección SQLite. |
| — | `LURACOIN_EXPLORER_INDEX_INTERVAL` | `2` segundos | Intervalo base entre pasadas del indexador. |

Ejemplo equivalente mediante variables de entorno:

```sh
export LURACOIN_EXPLORER_API=true
export LURACOIN_EXPLORER_INDEX=true
export LURACOIN_EXPLORER_PORT=19000
luracoin node --network testnet
```

El CLI no carga `.env` automáticamente. Las variables deben exportarse en la
shell o inyectarse mediante el gestor de procesos o contenedores utilizado.
Cuando se especifica una opción CLI, esta prevalece sobre el valor que sirvió
como predeterminado desde el entorno.
`--explorer-index` requiere que la API esté activa; combinarlo con
`--no-explorer-api` se rechaza como una configuración contradictoria.

## Endpoints

Todos los importes monetarios se expresan en **lurashis** y se devuelven como
strings decimales para no perder precisión al consumirlos desde JavaScript:
`1 LURA = 100.000.000 lurashis`. El contrato exacto de cada respuesta está
siempre disponible en `/openapi.json`.

### Disponibles sin SQLite

| Método y ruta | Descripción |
|---|---|
| `GET /health` | Salud del proceso y red configurada. |
| `GET /api/v1/status` | Altura, punta, sincronización, capacidades y progreso del índice. |
| `GET /api/v1/features` | Disponibilidad de la API core y del índice. |
| `GET /api/v1/blocks` | Bloques canónicos, del más reciente al más antiguo. |
| `GET /api/v1/blocks/{height-or-hash}` | Resumen de un bloque por altura o hash. |
| `GET /api/v1/blocks/{height-or-hash}/transactions` | Transacciones paginadas de un bloque. |
| `GET /api/v1/transactions/{txid}` | Transacción confirmada por ID. |
| `GET /api/v1/addresses/{address}` | Balance y nonce canónicos actuales. |

`GET /api/v1/blocks` acepta `limit`, `offset` y `before_height`. Su `limit`
máximo es 10 y cada bloque se carga por separado para mantener acotada la
memoria. El detalle del bloque no incluye todas sus transacciones: deben
solicitarse mediante la subruta paginada, cuyo `limit` máximo es 100.
Para recorrer bloques hacia atrás sin depender de un offset creciente, usa el
`pagination.next_before_height` de una respuesta como `before_height` de la
siguiente petición.

### Disponibles con el índice listo

| Método y ruta | Descripción |
|---|---|
| `GET /api/v1/transactions` | Feed histórico de transacciones. |
| `GET /api/v1/addresses` | Direcciones ordenadas por balance. |
| `GET /api/v1/addresses/{address}/transactions` | Historial completo de una dirección. |
| `GET /api/v1/stats` | Totales de bloques, transacciones, direcciones, fees, transferencias y recompensas. |

Las colecciones indexadas aceptan `limit` y `offset`, con un `limit` máximo de
100 en la API pública. Las respuestas incluyen siempre un objeto `pagination`
con `limit`, `offset`, `count` y, cuando está disponible, `total`.

Ejemplos:

```sh
curl -s http://127.0.0.1:18000/api/v1/blocks?limit=5
curl -s http://127.0.0.1:18000/api/v1/blocks/0
curl -s http://127.0.0.1:18000/api/v1/blocks/0/transactions?limit=25
curl -s http://127.0.0.1:18000/api/v1/stats
```

## Estado del índice y errores esperables

`GET /api/v1/status` y `GET /api/v1/features` exponen el estado del índice:

```json
{
  "enabled": true,
  "ready": false,
  "state": "building",
  "indexed_height": 1249,
  "target_height": 5000,
  "progress": 24.99
}
```

Los estados normales son:

| Estado | Significado |
|---|---|
| `disabled` | No se solicitó el índice y no se abre SQLite. |
| `building` | Se está realizando el backfill o alcanzando la punta. |
| `ready` | El índice alcanzó la altura canónica observada. |
| `error` | La última pasada falló; el nodo continúa y el indexador reintentará. |

Una ruta indexada que todavía no puede responder devuelve HTTP `503` con uno
de estos errores JSON:

- `explorer_index_disabled`
- `explorer_index_building`
- `explorer_index_error`
- `explorer_index_unavailable`

Las rutas core no dependen de este estado. Los IDs o direcciones mal formados
devuelven `400`, los bloques o transacciones inexistentes devuelven `404`, y
FastAPI devuelve `422` si un parámetro de query no satisface su tipo o límites.

No debe confundirse `status.ready`, que describe si el nodo está preparado,
con `status.index.ready`, que indica si SQLite alcanzó la punta observada. El
objeto `capabilities` permite comprobar directamente qué familias de consultas
pueden atenderse en ese momento.

## Qué almacena SQLite

La fuente de verdad sigue siendo la cadena canónica mantenida en los ficheros
de bloques y RocksDB. SQLite solo contiene una proyección para consultas:

- cabeceras y métricas resumidas de bloques;
- localización y campos públicos de transacciones;
- balances, actividad y totales agregados por dirección;
- relación entre direcciones y transacciones;
- estadísticas globales acumuladas;
- metadatos de esquema, red, cadena y progreso.

No se copian los bloques raw, firmas de desbloqueo ni material privado. Los
valores monetarios se almacenan como texto decimal para cubrir todo el rango
`uint64`. SQLite utiliza WAL y transacciones por bloque, por lo que también
pueden existir temporalmente los ficheros auxiliares `explorer.sqlite3-wal` y
`explorer.sqlite3-shm`.

La base puede crecer más que los bloques originales porque desnormaliza las
relaciones necesarias para búsquedas y rankings. Por eso su activación es
explícita. Construir `ExplorerIndex` no toca el sistema de ficheros; la base y
su directorio solo se crean cuando el servicio indexado se inicializa.

RocksDB conserva además el índice compacto canónico que ya utiliza el RPC de
wallet para localizar transacciones e historiales. Esta versión no lo vuelve
opcional: el flag controla únicamente la proyección SQLite ampliada.

## Backfill, reinicios y divergencias

El indexador procesa y confirma un bloque cada vez. Si el proceso se detiene a
mitad de un bloque, esa transacción SQLite se revierte y el siguiente arranque
reanuda desde el último bloque completo. Después del backfill consulta la punta
periódicamente y añade únicamente los bloques nuevos.

Antes de continuar valida la versión del esquema, `network`, `chain_id` y el
último bloque indexado. Una base perteneciente a otra red se rechaza para evitar
mezclar datos. Si el prefijo previamente indexado pertenece a la misma red pero
ya no coincide con la cadena canónica local, la proyección se reconstruye desde
la fuente de verdad. Un fallo del indexador nunca invalida un bloque ni detiene
el full node; los reintentos usan espera exponencial, con un máximo de 60
segundos.

Para reconstruir manualmente el índice, detén primero el nodo y mueve a una
copia de seguridad, como una unidad, `explorer.sqlite3` y sus posibles ficheros
`-wal` y `-shm`. Al arrancar de nuevo con `--explorer-index`, Luracoin creará
una proyección nueva desde la cadena canónica. Todavía no existe un comando
independiente `reindex`.

## Integración con el frontend público

`luracoin-website` consume la URL base mediante una variable pública de build:

```sh
PUBLIC_EXPLORER_API_URL=https://explorer-api.example.com npm run build
```

La URL debe apuntar a esta API y nunca al RPC privado `/v1`. El navegador añade
por sí mismo rutas como `/api/v1/status` o `/api/v1/blocks`; por tanto, configura
solo el origen base y no una ruta concreta.

## Exposición y límites de seguridad

El bind predeterminado `127.0.0.1` evita la exposición accidental. La API es
read-only, no requiere autenticación y permite peticiones CORS `GET` desde
cualquier origen, por lo que `--explorer-host 0.0.0.0` debe ser una decisión
operativa explícita. Para publicarla en Internet utiliza un reverse proxy con
TLS, límites de peticiones, límites de respuesta, timeouts y observabilidad.
El servidor no incorpora rate limiting ni cuotas de disco para SQLite.

La API informa `confirmations` como profundidad observada en la cadena local.
No representa finalidad: Luracoin todavía no implementa selección de cadena
por trabajo acumulado ni reorganizaciones.
