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
```
{
    "input": "78D5A1F3F42F7DDE5830E57A2FAF233FF3E2B714B8758997F3E20C9A5396968F",
    "mnemonic": "juice public language tribe water upset general bronze kick latin silver lend dilemma fortune fancy attitude maze sauce weasel bomb pioneer slender focus tooth",
    "seed": "adbbd00699b49ca4cc0103baab21e4c7991a3a3edc23078568c7cde8d1f4103c1727644f7f4e45e5277948485e74ae32048ea37db07f340cf0e6e24314cd02b9",
    "xprv": "xprv9s21ZrQH143K2ckdHwDZcdDqzW8ayRXVGxHGfQCfUKeeJKw26qV8kU7LsEcLomFjnXCBzQVEsBvMxVYQ1yjBz7S2QQ4DCXSYj6LFs7cc366",
    "private_key": "0686758824778a0f46651f4a63b149f6704d003852b0fc1bc04c3ba71d6866f7",
    "public_key": "03ca8b1d828b4147ee31b181d5ae3d28f49c0f611faf8bd5d83eb0425069cdea93",
    "address": "1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP"
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
32-byte block hash -> Each record stores:
    > Size of the block (4 bytes)
    > Serialized Block
```  