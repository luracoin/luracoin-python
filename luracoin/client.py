#!/usr/bin/env python3

"""
Luracoin client

Usage:
  client.py mine 

Options:
  -h --help            Show help
  -w, --wallet PATH    Use a particular wallet file (e.g. `-w ./wallet2.dat`)
  -n, --node HOSTNAME  The hostname of node to use for RPC (default: localhost)
  -p, --port PORT      Port node is listening on (default: 9999)
"""
import sys
sys.path.append('../')

import os
import socket
import binascii
import shutil
import plyvel
from docopt import docopt
from luracoin.pow import proof_of_work
from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.transactions import Transaction, TxIn, TxOut, OutPoint
from luracoin.wallet import build_p2pkh


def main(args):
    if args['mine']:
        mine()

def mine():
    coinbase1 = Transaction(
        version=1,
        txins=[
            TxIn(
                to_spend=OutPoint(Config.COINBASE_TX_ID, Config.COINBASE_TX_INDEX),
                unlock_sig="0",
                sequence=0,
            )
        ],
        txouts=[
            TxOut(
                value=3_000_000_000,
                to_address=build_p2pkh("1QHxaBNsCtYXj8M6CUi7fUeNY2FE2m7t8e"),
            ),
            TxOut(
                value=1_500_000_000,
                to_address=build_p2pkh("16iFwTZFLhDVY3sK1K3oBRLNkJCjHBJv1E"),
            ),
            TxOut(
                value=500_000_000,
                to_address=build_p2pkh("1ByCQKMDiRM1cp14vrpz4HCBz7A6LJ5XJ8"),
            ),
        ],
        locktime=0,
    )

    block = Block(
        version=1,
        prev_block_hash=Config.COINBASE_TX_ID,
        timestamp=1_501_821_412,
        bits=24,
        nonce=0,
    )

    block.txns = [coinbase1]
    print(block.id)
    print("Mining")
    print("======")
    proof = proof_of_work(block, 3)
    print("======")
    block.nonce = proof
    block.generate_hash()
    print(block.id)
    print("Solved")


if __name__ == '__main__':
    main(docopt(__doc__, version='luracoin client 0.1'))