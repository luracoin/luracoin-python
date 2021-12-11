# Luracoin
![](https://travis-ci.com/luracoin/luracoin-python.svg?branch=master)
![](https://img.shields.io/badge/code%20style-black-000000.svg)
![](https://img.shields.io/badge/status-in%20development-red.svg)

Luracoin Python implementation.

I am creating this to learn more about cryptocurrencies. It is an __*educational project*__.

## Status
Early development. The blockchain is not live yet.


## FAQ
#### Why python?
It's easy and fun. We don't need performance yet, we need more contributors. I will also create a Go implementation.

#### Diferences with Bitcoin 
- 2 more bytes on the header (Nonce).  
- Block time every 3 min instead of 10 min.  
- Progressive block size limit instead of 1MB.
- No max supply, there will be a constant tail emission
- Account Model instead of UTXO
- Each transaction has exactly 179 bytes


## Install

#### MacOS
```shell
brew install rocksdb
```


## Testing
For testing use ```pytest```
```shell
pytest -v
```

## Run commands
```
python -m luracoin.client COMAND_NAME
```

#### Generate address

```
python -m luracoin.client generateAddress
```

Response:
```json
{
    "input": "105B4F699175E425688714FC880CF9069894A3D5D7EBB87CC340EDAB9B14E979",
    "mnemonic": "aware surprise surprise carry furnace bargain pear tip wish document dinner artwork matter faint firm word reveal toward south swap rifle media planet capital",
    "seed": "b3bdaf77cf6e3cc5e2e5be9d2e3d8747f97466ca36906524caa0d702c8cc62f2cc13afc84aabeb0cb91a63302bdc8227b1a8d7358bde66b381c411401a5e8a85",
    "xprv": "xprv9s21ZrQH143K4J9bUMHy8UEQBY8CGfyPj4pzK26SDtX1qe9z7NWAhwyAEdHpJxYKjJJhpB1a3edg8vjvjEYvg8q5VVzB6q8UZ9Jrz97RegT",
    "private_key": "b5d1e2143c234a9949066ee5199a79192e78f4127893dc00eefb28a0b8a64078",
    "public_key": "031171ab965a7ccd1ee72bf1d95251ede9bb07049e1df91ef4f6b7349c2bf4fe3e",
    "verifying_key": "1171ab965a7ccd1ee72bf1d95251ede9bb07049e1df91ef4f6b7349c2bf4fe3e5098089791c7c46a858f8a362f9cba7d75a3253340462e7e35b1320cdab3957f",
    "address": "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"
}
```

## Blocks

Each block header has 118 bytes.

- version (4 bytes)
- id (32 bytes)
- miner (34 bytes)
- prev_block_hash (32 bytes)
- height (4 bytes)
- timestamp (4 bytes)
- bits (4 bytes)
- nonce ( 4 bytes)
- transaction list (each transaction 179 bytes)



## RocksDB 

#### Chainstate:

```
'file_number' -> Actual file number (eg. 5 that will turn into blk0004.dat)  
'height' -> Current block height
'validation' -> Validation process
'b' + 32-byte block hash -> block height record.
't' + 32-byte transaction id -> Each record stores:
    > Block height (4 bytes)
    > Transaction position inside the block (2 bytes)
'a' + 34-byte address ->
    > Balance
    > Committed
```

#### Blocks:
```
4-byte block height -> Each record stores:
    > Size of the block (4 bytes)
    > Serialized Block
```  
