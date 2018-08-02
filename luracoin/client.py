#!/usr/bin/env python3
"""
Luracoin client

Usage:
  client.py startBlockchain <address>
  client.py getBlock <block_hash>
  client.py sendTransaction
  client.py getWallet
  client.py getBlockchainInfo
  client.py getMempool
  client.py getChainstate
  client.py start
  client.py mine 
  client.py tx

Options:
  -h --help            Show help
  -w, --wallet PATH    Use a particular wallet file (e.g. `-w ./wallet2.dat`)
  -n, --node HOSTNAME  The hostname of node to use for RPC (default: localhost)
  -p, --port PORT      Port node is listening on (default: 9999)

"""
import logging
import os
import socket
import binascii
import pprint
import shutil
import plyvel
from .transactions import TxOut, TxIn, UnspentTxOut, Transaction, OutPoint, deserialize_transaction, build_p2pkh, search_utxo, utxo_valid, utxo_value
from docopt import docopt
from random import randint
from .config import Config
from .blocks import Block, serialize_block, deserialize_block, find_block_in_file, add_block_to_chain, recieve_block
from .network import ThreadedTCPServer, TCPHandler, GetMempoolMsg, encode_socket_data, read_all_from_socket
from .helpers import get_blk_file_size
from .wallet import get_wallet, address_to_pubkey
from .pow import proof_of_work, valid_proof
import threading
import logging
import socketserver
import socket
import time
from ecdsa import VerifyingKey
from ecdsa import SigningKey
import ecdsa
import hashlib
from base58 import b58encode_check
import json


logging.basicConfig(
    level=getattr(logging, os.environ.get('TC_LOG_LEVEL', 'INFO')),
    format='[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main(args):
    if args['getBlock']:
        get_block(args)
    elif args['startBlockchain']:
        start_blockchain(args)
    elif args['start']:
        start(args)
    elif args['getMempool']:
        get_mempool(args)
    elif args['sendTransaction']:
        send_transaction(args)
    elif args['mine']:
        mine_forever()
    elif args['getWallet']:
        getWallet()
    elif args['tx']:
        tx()
    elif args['getBlockchainInfo']:
        getBlockchainInfo()
    elif args['getChainstate']:
        getChainstate()


def getChainstate():
    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    info = {}
    for key, value in db:
        info[key.decode()] = value.decode()

    info['size'] = len(info)
    db.close()
    print(json.dumps(info, indent=4))


def getBlockchainInfo():
    db = plyvel.DB(Config.BLOCKS_DIR + 'index', create_if_missing=True)
    key_values = {}

    heigth = db.get(b'b')
    blk_file = db.get(b'l')

    for key, value in db:
        key_values[key.decode()] = value.decode()

    info = {
        "heigth": heigth.decode('utf-8'),
        "blk_file": blk_file.decode('utf-8'),
        "database": key_values
    }

    db.close()
    print(json.dumps(info, indent=4))


def tx():
   block = find_block_in_file(15786, '000000')
   print(block)
   block = find_block_in_file(15787, '000000')
   print(block)



def getWallet():
    address = get_wallet()
    pub_key = address_to_pubkey(address[2])
    utxo = search_utxo(address[2])
    utxo_available = {}

    balance = 0
    balance_pending = 0

    for k, v in utxo.items():
        tx_id = k[1:65]
        vout = k[65:]
        if utxo_valid(tx_id, vout):
            utxo_available[k] = v
            balance = balance + utxo_value(tx_id, vout)
        else:
            balance_pending = balance_pending + utxo_value(tx_id, vout)

    info = {
        "address": address[2],
        "pub_key": pub_key,
        "balance": balance / 100_000_000,
        "balance_pending": balance_pending / 100_000_000
        #"utxo": utxo,
        #"utxo_available": utxo_available
    }

    print(json.dumps(info, indent=4))


def get_block(args):
    '''
    Example:
    > python client.py getBlock 2fe2be6f555259c9a0c6ab989786f728ef8d1fa50c1d8d6dc20ce77fb004775d
    '''
    db = plyvel.DB(Config.BLOCKS_DIR + 'index', create_if_missing=True)
    result = db.get(b'b' + args['<block_hash>'].encode())
    print(result)
    db.close()
    return result


def start(args):
    peer_hostnames = {p for p in os.environ.get('TC_PEERS', '').split(',') if p}
    PORT = os.environ.get('TC_PORT', 9999)
    workers = []
    server = ThreadedTCPServer(('0.0.0.0', PORT), TCPHandler)

    def start_worker(fnc):
        workers.append(threading.Thread(target=fnc, daemon=True))
        workers[-1].start()

    logger.info(f'[p2p] listening on {PORT}')
    start_worker(server.serve_forever)

    if peer_hostnames:
        logger.info(
            f'start initial block download from {len(peer_hostnames)} peers')
        send_to_peer(GetBlocksMsg(active_chain[-1].id))
        ibd_done.wait(60.)  # Wait a maximum of 60 seconds for IBD to complete.

    start_worker(mine_forever)
    [w.join() for w in workers]



def mine_forever():

    while True:
        db = plyvel.DB(Config.BLOCKS_DIR + 'index', create_if_missing=True)
        print("Minig...")
        heigth = db.get(b'b')
        blk_file = db.get(b'l')
        db.close()

        last_block = find_block_in_file(heigth.decode('utf-8'), blk_file.decode('utf-8'))
        proof = proof_of_work(last_block.id)

        tx_out = TxOut(value=5000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig=str(int(heigth.decode()) + 1), sequence=0)

        tx = Transaction(
            version=1,
            txins=[tx_in],
            txouts=[tx_out],
            locktime=None
        )

        genesis_block = Block(
            version=1,
            prev_block_hash=last_block.id,
            timestamp=1501821412,
            bits=24,
            nonce=proof,
            txns=[tx])

        genesis_block.pretty_print()

        serialized_block = serialize_block(genesis_block)

        recieve_block(serialized_block)



def get_mempool(args):
    mempool = send_msg(GetMempoolMsg())
    print(mempool)


def send_transaction(args):
    tx_out = TxOut(value=5000000000, to_address="1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS")
    tx_out2 = TxOut(value=15000000000, to_address="1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS")
    tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)
    tx_in2 = TxIn(to_spend=OutPoint(0, -1), unlock_sig='1', sequence=0)

    tx = Transaction(
        version=1,
        txins=[tx_in],
        txouts=[tx_out],
        locktime=None
    )

    tx = tx.serialize_transaction()

    logger.info(f'built txn {tx}')

    command = binascii.hexlify(str("txn").encode())
    command = command.decode('utf-8').ljust(24, '0')

    msg = Config.MAGIC_BYTES + command + tx

    send_msg(msg)


def start_blockchain(args):
    '''
    Deletes all the data an initializes the new Blockchain.
    Example:
    > python client.py startBlockchain 1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS
    '''
    folder = Config.BLOCKS_DIR
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    tx_out = TxOut(value=5000000000, to_address=build_p2pkh(args['<address>']))
    tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)

    tx = Transaction(
        version=1,
        txins=[tx_in],
        txouts=[tx_out],
        locktime=None
    )

    genesis_block = Block(
        version=1,
        prev_block_hash=0,
        timestamp=1501821412,
        bits=24,
        nonce=10126761,
        txns=[tx])

    genesis_block.pretty_print()

    serialized_block = serialize_block(genesis_block)

    recieve_block(serialized_block)



def send_msg(data: bytes, node_hostname=None, port=None):
    node_hostname = getattr(send_msg, 'node_hostname', 'localhost')
    port = getattr(send_msg, 'port', 9999)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((node_hostname, port))
        s.sendall(encode_socket_data(data))
        return read_all_from_socket(s)


if __name__ == '__main__':
    main(docopt(__doc__, version='luracoin client 0.1'))
