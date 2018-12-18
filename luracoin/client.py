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
from docopt import docopt


def main(args):  # type: ignore
    if args['mine']:
        mine()


def mine():  # type: ignore
    pass


if __name__ == '__main__':
    main(docopt(__doc__, version='luracoin client 0.1'))  # type: ignore
