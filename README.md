# Luracoin
![](https://travis-ci.com/maguayo/luracoin-python.svg?branch=master)
![](https://img.shields.io/badge/code%20style-black-000000.svg)
![](https://img.shields.io/badge/status-in%20development-red.svg)

Luracoin Python implementation.

## Status
Early development. The blockchain is not live yet.


## FAQ
#### Why python?
It's easy and fun. We don't need performance yet, we need more contributors. I will also create a Go implementation.

#### Diferences with Bitcoin 
- 2 more bytes on the header (Nonce).  
- Block time every 5 min instead of 10 min.  
- 4MB limit instead of 1MB.
- Supply of 21 billion coins instead of 21 million.


## Testing
For testing use ```pytest```
```shell
pytest -v
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
