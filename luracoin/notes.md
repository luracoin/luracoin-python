TODO:

1.- Blocks
2.- Save blocks
3.- Mine blocks
4.- Coinbase Tx
5.- UTXO


``` python
# Cuantos Int en bytes 2**(8*4)
```



We will use pickleDB to store the data. We will have two databases:

- Block index

'b' + 32-byte block hash -> 
	- (4 bytes) The height.
	- (82 bytes) The block header.
	- (4 bytes) The number of transactions.
	- (4 bytes) In which file, and where in that file, the block data is stored.


'f' + 4-byte file number -> file information record. Each record stores:
	- (2 bytes) The number of blocks stored in the block file with that number.
	- (4 bytes) The size of the block file with that number ($DATADIR/blocks/blkNNNNN.dat).
	- (8 bytes) The lowest and highest height of blocks stored in the block file with that number.
	- (8 bytes) The lowest and highest timestamp of blocks stored in the block file with that number.




- Cain State (UTXO)

'c' + 32-byte transaction hash -> unspent transaction output record for that transaction. These records are only present for transactions that have at least one unspent output left. Each record stores:
	- The version of the transaction.
	- Whether the transaction was a coinbase or not.
	- Which height block contains the transaction.
	- Which outputs of that transaction are unspent.
	- The scriptPubKey and amount for those unspent outputs.
'B' -> 32-byte block hash: the block hash up to which the database represents the unspent transaction outputs.
