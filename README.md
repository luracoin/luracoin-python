# Luracoin
![](https://travis-ci.com/luracoin/luracoin-python.svg?branch=master)
![](https://img.shields.io/badge/code%20style-black-000000.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
![](https://img.shields.io/badge/status-in%20development-red.svg)

Luracoin Python implementation.

I am creating this to learn more about cryptocurrencies. It is an __*educational project*__. This project is WIP, not stable on master yet.

## Status
Early development. The blockchain is not live yet.


## FAQ
#### Why python?
It's easy and fun. We don't need performance yet, we need more contributors. I will also create a Go implementation.

#### Why are you using msgpack?
It's worst than simple byte serialization, like 1.5x worst, but this is an educational project, I don't expect many transactions.

#### Diferences with Bitcoin 
- 2 more bytes on the header (Nonce).
- The Coinbase can be spend after 7 blocks.
- No UTXO, Luracoin uses Account Based Model
- Progressive Block time starting every 60 min and after every halving decrese the time to a maximum of 5 minutes. (WIP)
- The blocksize instead of 1MB, will start at 100Kb with an increase of 20% every 8640 blocks (3 months)
- Supply of 21 billion coins instead of 21 million.
- Account Balances commitment every 2 weeks.


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
python -m luracoin.client generateWallet
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

## LevelDB 

#### Block keys:

```
'l' -> Actual file number (eg. blk00045.dat)  
'b' -> Current block height
'c' -> Validation process

'b' + 32-byte block hash -> block index record. Each record stores:  
	The block header.  
	The height.  
	The number of transactions.  
	To what extent this block is validated.  
	In which file, and where in that file, the block data is stored.

'b' + 6-byte block height -> 
	6-byte File name in which the block data is stored.
	32-byte block hash
```
  

#### Chainstate keys:

```
'c' + 32-byte transaction id -> Outputs. Each record stores:  
    TX Version (4 bytes).
    Coinbase (1 byte).
    Block height (4 bytes).
    Num Outputs (VarInt).
    Outputs:
        Output Length (VarInt).
        Output.

```



### Installr BerkeleyDB
```
brew install berkeley-db@4
echo 'export PATH="/usr/local/opt/berkeley-db@4/bin:$PATH"' >> ~/.zshrc
BERKELEYDB_DIR=$(brew --prefix berkeley-db@4) pip install bsddb3
```

Examine BerkleyDB:
```
db_dump -p chain/bsddb.bdb 
```
