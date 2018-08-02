from typing import Iterable, NamedTuple, Union
import logging
from .config import Config
import os
import hashlib
import binascii
from .wallet import init_wallet
from .transactions import TxOut, TxIn, UnspentTxOut, Transaction, OutPoint, deserialize_transaction, validate_tx, remove_tx_from_chainstate, add_tx_to_chainstate
from .pow import validate_pow
from .helpers import var_int, get_blk_file_size, sha256d
import plyvel


class Block(NamedTuple):
    # A version integer.
    version: int

    # A hash of the previous block's header.
    prev_block_hash: str

    # A UNIX timestamp of when this block was created.
    timestamp: int

    # The difficulty target; i.e. the hash of this block header must be under
    # (2 ** 256 >> bits) to consider work proved.
    bits: int

    # The value that's incremented in an attempt to get the block header to
    # hash to a value below `bits`.
    nonce: int

    # Transaction list
    txns: list

    def pretty_print(self):
        print("===========\n")
        print("Version: " + str(self.version))
        print("Hash: " + self.id)
        if self.prev_block_hash != 0:
            print("Prev Hash: " + str(self.prev_block_hash))
        else:
            print("Prev Hash: - ")
        print("Timestamp: " + str(self.timestamp))
        print("Bits: " + str(self.bits))
        print("Nonce: " + str(self.nonce))
        print("Transactions: ")
        for t in self.txns:
            print("\tID: " + str(t.id))
            print("\tCoinbase: " + str(t.is_coinbase))
            print("\tTxouts: " + str(t.txouts))
            print("\tTxins: " + str(t.txins))
            print("\n")
        print("===========\n")

    @property
    def id(self) -> str:
        txns_ids = ''
        for t in self.txns:
            txns_ids = txns_ids + t.id

        string_to_hash = str(self.version) + str(self.prev_block_hash) + str(
            self.timestamp) + str(self.bits) + str(self.nonce) + str(txns_ids)

        block_id = sha256d(string_to_hash)
        return block_id


def serialize_block(block):
    '''
    Magic bytes (4 bytes)
    Block header (82 bytes)
    -> Block version (4 bytes)
    -> Prev hash (32 bytes)
    -> Block hash (32 bytes)
    -> Difficulty bits (4 bytes)
    -> Timestamp (4 bytes)
    -> Nonce (6 bytes)
    '''
    version = block.version.to_bytes(4, byteorder='little', signed=False).hex()

    if block.prev_block_hash == 0:
        prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    else:
        prev_hash = block.prev_block_hash

    bits = block.bits.to_bytes(4, byteorder='little', signed=False).hex()
    timestamp = block.timestamp.to_bytes(4, byteorder='little', signed=False).hex()
    nonce = block.nonce.to_bytes(6, byteorder='little', signed=False).hex()
    total = Config.MAGIC_BYTES + version + prev_hash + block.id + bits + timestamp + nonce

    # Tx_count
    tx_count = var_int(len(block.txns))
    total = total + tx_count

    # Tx_data
    for tx in block.txns:
        total = total + tx.serialize_transaction()

    return total


def recieve_block(block):
    '''
    Triggered when you recieve a block over the P2P network or when you create one. This function
    Validate the block and add it to the chain.

    :param block: Block object
    '''
    if validate_block(block):
        add_block_to_chain(block)


def validate_block(block):
    '''
    Validate a block.

    :param block: Block object
    :return: Boolean
    '''
    block = deserialize_block(block)
    if validate_pow(block) and validate_basics(block) and validate_transactions(block):
        return True


def validate_basics(block):
    '''
    Validate block basics.
        - prev_block_hash + Current height
        - Bits
        - Size
        - Reward + Fees
        - Timestamp

    :param block: Block object
    :return: Boolean
    '''
    return True


def validate_transactions(block):
    '''
    Validate all transactions in a block.

    :param block: Block object
    :return: Boolean
    '''
    valid = True
    for tx in block.txns:
        if not validate_tx(tx):
            valid = False

    return valid


def deserialize_block(serialized_block):
    magic = serialized_block[0:8]
    version = serialized_block[8:16]
    prev_hash = serialized_block[16:80]
    block_hash = serialized_block[80:144]
    bits = serialized_block[144:152]
    timestamp = serialized_block[152:160]
    nonce = serialized_block[160:172]

    block = Block(
        version=int.from_bytes(binascii.unhexlify(version), byteorder='little'),
        prev_block_hash=prev_hash,
        timestamp=int.from_bytes(binascii.unhexlify(timestamp), byteorder='little'),
        bits=int.from_bytes(binascii.unhexlify(bits), byteorder='little'),
        nonce=int.from_bytes(binascii.unhexlify(nonce), byteorder='little'),
        txns=[]
    )

    txns = deserialize_transaction(serialized_block[172:])
    for t in txns:
        block.txns.append(t)

    return block


def blk_to_list(blk_number: str, raw: bool=False) -> list:
    '''
    Get the contents of a blk file and create a list with all blocks within.

    :param blk_number: <String> Filename (eg. 026113)
    :return: <List>
    '''
    try:
        f = open(Config.BLOCKS_DIR + "blk" + blk_number + ".dat", 'r')
        contents = f.read()
        f.close()
        block_list = contents.split(Config.MAGIC_BYTES)
        block_list = [l for l in block_list if l]
        if not raw:
            block_list = [deserialize_block(bl) for bl in block_list]
        return block_list
    except FileNotFoundError:
        return []


def find_block_in_file(blk_height: int, blk_file: str):
    blk_list = blk_to_list(blk_file)

    for bl in blk_list:
        if int(bl.txns[0].txins[0].unlock_sig) == int(blk_height):
            return bl



def next_blk_file(current_blk_file: str) -> str:
    '''
    Increases by one the blk file name, for example:
    blk000132.dat => blk000133.dat

    :param current_blk_file: <String> Actual file (eg. 000001)
    :return: <String> Next file (eg. 000002)
    '''
    return str(int(current_blk_file) + 1).zfill(6)



def process_block_transactions(block):
    '''
    Add outputs to the chainstate and delete the inputs used.
    '''
    for tx in block.txns:
        for tx_spent in tx.txins:
            if tx_spent.to_spend.txid != 0:
                remove_tx_from_chainstate(tx_spent.to_spend.txid, tx_spent.to_spend.txout_idx)

        add_tx_to_chainstate(tx, int(block.txns[0].txins[0].unlock_sig))



def add_block_to_chain(serialized_block):
    '''
    Save a serialized block in "blkXXXXX.dat file". If the current file size is greater than 
    Config.MAX_FILE_SIZE then we'll create another file and save the numberinfo LevelDB.

    Data:
    [  magic bytes ]  <- 4 bytes
    [     size     ]  <- 4 bytes
    [ block header ]  <- 80 bytes
    [   tx count   ]  <- varint
    [    TX data   ]  <- remainder
    '''
    # Deserialize block
    deserialize_blk = deserialize_block(serialized_block)

    if validate_block(serialized_block):
        # Substract the length of the Magic Numbers
        size_block = int(len(serialized_block) - 8).to_bytes(4, byteorder='little', signed=False).hex()
        serialized_block = serialized_block[:8] + size_block + serialized_block[8:]

        # Get the current file
        db = plyvel.DB(Config.BLOCKS_DIR + 'index', create_if_missing=True)
        last_blk_file = db.get(b'l')
        
        # If there is not a current file we'll start by '000000'
        if last_blk_file is None or last_blk_file == '' or last_blk_file == b'':
            last_blk_file = '000000'
        else:
            last_blk_file.decode('utf-8')

        # If the actual file size is greater or equal to MAX_FILE_SIZE we'll increase it by one
        if get_blk_file_size("blk" + str(last_blk_file) + ".dat") >= Config.MAX_FILE_SIZE:
            last_blk_file = next_blk_file(last_blk_file)

        try:
            last_blk_file = last_blk_file.encode()
        except AttributeError:
            pass

        try:
            f = open(Config.BLOCKS_DIR + "blk" + last_blk_file.decode() + ".dat", 'ab+')
            contents = f.read()
            f.close()
        except FileNotFoundError:
            contents = b''

        with open(Config.BLOCKS_DIR + "blk" + last_blk_file.decode() + ".dat", "ab+") as f:
            f.write(contents + serialized_block.encode())

        # Save the current file number
        db.put(b'l', last_blk_file)
        db.put(b'b', deserialize_blk.txns[0].txins[0].unlock_sig.encode())
        db.close()

        process_block_transactions(deserialize_blk)
