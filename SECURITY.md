# Security policy

Luracoin is an educational, pre-release project. It is not approved for
mainnet use and must not be used to secure assets with real-world value.

## Supported environments

Only the current `master` branch is supported. The default runtime network is
`testnet`; selecting `mainnet` does not mean a public mainnet is available.

A historical README revision published wallet material associated with the
development genesis, and that material remains recoverable from repository
history. The address is compromised by design and must never be used for a
future public genesis or to hold funds.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting / Security Advisory flow
for the repository. Do not open a public issue containing private keys, seed
phrases, weaponized proof-of-concept code, or details that would put users at
immediate risk.

Include the affected commit, impact, reproduction conditions, and a suggested
mitigation when possible.

## Secret handling

- Never commit mnemonics, seeds, extended private keys, or private keys.
- Test vectors must be explicitly labelled as public and must never receive
  funds.
- A future genesis ceremony must use newly generated, independently verified
  key material and publish only the public address.
- The optional wallet web gateway must remain local. Its RPC bearer is
  server-side only and must never be copied into frontend assets, browser
  storage, URLs, logs or responses.

## Local service exposure

The private RPC must always bind to loopback. The wallet web server also binds
to `127.0.0.1` by default. `--wallet-host 0.0.0.0` is only for a container whose
port is published as `127.0.0.1:8080:8080` on the host; publishing it on all
interfaces or placing it behind a public reverse proxy is unsupported and
unsafe.
