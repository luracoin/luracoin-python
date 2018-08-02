# Luracoin
Luracoin Python implementation.

## Status
Early development

## TODO:
- Transactions
	- Validate transaction
		- TXIN / TXOUT not empty
		- Max Block size
		- Max money supply
		- Script unlock and validate it
- Mining
	- Get transactions from the mempool
	- Validate transactions and block
	- Difficulty
- Validate block
	- Do not repeat blocks
	- Max Block size
	- Nonce
	- Hash
	- Coinbase transaction
	- Transactions inside
	- Timestamp
- Validate chain and resolve conflicts.
- Work with Bytes and Binary instead of Text.
- Choose where to save the data and config folder.
- Add Multisig and other Script OP_CODES.
- Merkle Tree.
- Basic GUI wallet for iOS/Windows/Linux.


## FAQ
#### Why python?
It's easy and fun. We don't need performance yet, we need more contributors.

#### Diferences with Bitcoin 
- 2 more bytes on the header (Nonce).  
- Block time every 5 min instead of 10 min.  
- 4MB limit instead of 1MB.  



## Testing
```shell
python -m unittest discover -s tests -p '*_test.py' -v
```

## LevelDB keys

```shell
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