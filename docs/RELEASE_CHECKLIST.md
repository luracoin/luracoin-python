# Checklist de release

Este checklist evita confundir un build correcto con una red segura. Marca
cada punto con evidencia enlazable. Una release alpha puede dejar apartados de
mainnet abiertos; una release mainnet no.

## Para toda release

- [ ] El árbol de trabajo contiene únicamente cambios revisados e
  intencionales.
- [ ] No hay mnemonics, seeds, xprv, claves privadas, tokens RPC ni wallets
  reales/no declarados en código, documentación, fixtures, logs o artefactos.
- [ ] Cualquier clave conocida imprescindible para un vector está marcada como
  pública, separada de ejemplos de usuario y su dirección no se usa con valor.
- [ ] `python -m compileall -q luracoin` pasa.
- [ ] La suite completa pasa con una instancia Redis limpia.
- [ ] Cobertura de `luracoin` es al menos 80 % y no bajó en consenso/P2P/RPC.
- [ ] `uv lock --check` confirma que `uv.lock` corresponde a `pyproject.toml`.
- [ ] `uv build --clear --python python` produce sdist y wheel, y
  `uv run twine check --strict dist/*` valida ambos sin avisos.
- [ ] El sdist contiene licencia, metadatos, changelog, política de seguridad,
  migración, protocolo, vectores, lock y la suite fuente completa.
- [ ] El wheel se instala con sus dependencias en un entorno vacío;
  `luracoin --help` y `import luracoin` funcionan desde ese entorno.
- [ ] Se probaron Python 3.10, 3.11 y 3.12 en CI.
- [ ] Dependencias bloqueadas/actualizadas han sido revisadas por licencias,
  vulnerabilidades y cambios de comportamiento.
- [ ] El export de dependencias de runtime pasa `pip-audit` sin vulnerabilidades
  conocidas; dependencias de desarrollo no se mezclan con ese resultado.
- [ ] Se verificó un nodo desde data-dir vacío y otro desde datos de la versión
  anterior.
- [ ] Reinicio, señales y cierre no dejan sockets, locks o bases sin cerrar.
- [ ] El changelog identifica cambios incompatibles de consenso, disco, P2P y
  RPC.
- [ ] La documentación de protocolo coincide con los vectores y el código.

## Red y RPC

- [ ] Nodos v2 completan handshake, discovery, sync, ping/pong y relay en una
  prueba TCP real.
- [ ] Nodos rechazan magic, chain ID, versión, checksum, longitud y payload
  incorrectos.
- [ ] Se probaron límites de peers, payload, inventario, tiempo y memoria bajo
  entradas hostiles.
- [ ] RPC solo enlaza loopback y rechaza cualquier host remoto.
- [ ] `rpc.token` es impredecible, persistente, de longitud suficiente y modo
  `0600`; symlinks/owner inesperado se rechazan.
- [ ] Ningún log, error, crash report o renderer Electron recibe el bearer
  token.
- [ ] El wallet web no contiene el bearer y solo expone la allowlist
  `/wallet-api/*`; Host/Origin/Fetch Metadata, cookie HttpOnly/Strict, límites y
  ausencia de CORS tienen pruebas negativas.
- [ ] Si `--wallet-host 0.0.0.0` se usa en contenedor, el puerto se publica como
  `127.0.0.1:8080:8080`; el RPC sigue sin publicarse y enlaza loopback.
- [ ] La API devuelve importes como strings y diferencia admisión, rechazo,
  error de Redis y confirmación.

## Persistencia y consenso

- [ ] Génesis, recompensa, halvings, tail emission, dificultad y hashes
  coinciden con vectores fijados.
- [ ] Se probaron doble coinbase, doble gasto intra-bloque, nonce repetido,
  firma high-S, chain ID ajeno, prev hash y bits incorrectos.
- [ ] Reintentar el mismo bloque no duplica balances, recompensa ni índices.
- [ ] Se probaron procesos interrumpidos durante append, batch de cuentas e
  indexado, además de recuperación posterior.
- [ ] Rotación de `blkNNNN.dat`, fichero truncado, corrupción y disco lleno
  tienen resultados definidos y seguros.
- [ ] Redis caído no corrompe cadena ni se interpreta como una transacción
  confirmada.

## Release de testnet pública

- [ ] Se mantiene explícitamente la etiqueta «sin valor real» en CLI, wallet,
  faucet, explorer y documentación.
- [ ] Se han implementado y probado chainwork, forks y reorganizaciones, o la
  red se anuncia claramente como experimento lineal no resistente a forks.
- [ ] Hay al menos dos seeds independientes con monitorización y runbooks.
- [ ] Faucet y explorer están aislados de mainnet/devnet.
- [ ] Se completó un soak test multi-nodo con particiones, latencia, peers
  maliciosos, reinicios y bloques simultáneos.
- [ ] Existe procedimiento de reset coordinado, porque una testnet alpha puede
  requerirlo.
- [ ] Se ha hecho revisión independiente del alcance de la release.

## Puerta de mainnet — todo obligatorio

- [ ] Consenso soporta forks, selección por trabajo acumulado y reorg atómica.
- [ ] Existe especificación de consenso versionada y congelada.
- [ ] Una implementación/verificador independiente reproduce todos los
  vectores.
- [ ] Se realizó una ceremonia de génesis nueva, documentada y auditada; no se
  reutilizó ninguna clave o dirección de desarrollo.
- [ ] Distribución inicial y custodia han sido revisadas y publicadas.
- [ ] Auditoría externa cubre consenso, criptografía, P2P, almacenamiento, RPC,
  wallet y cadena de suministro, y todos los hallazgos críticos/altos están
  cerrados.
- [ ] Testnet pública cumplió los criterios de estabilidad acordados.
- [ ] Builds son reproducibles, firmados y acompañados de checksums y SBOM.
- [ ] Hay proceso de respuesta a incidentes, divulgación privada, rotación de
  operadores y actualización coordinada.
- [ ] El manifiesto mainnet está fijado y `initialize_chain()` lo valida byte a
  byte.

Mientras cualquier punto de esta sección esté abierto, mainnet debe seguir
fallando cerrado.
