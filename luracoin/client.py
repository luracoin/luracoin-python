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

def main(args):
    if args['mine']:
        mine()

def mine():
    print("Mining")
    proof = proof_of_work("656933", 5)
    print(proof)
    print("Solved")


if __name__ == '__main__':
    main(docopt(__doc__, version='luracoin client 0.1'))