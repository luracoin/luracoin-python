#!/usr/bin/env python3

"""
Luracoin client

Usage:
  client.py generateWallet [--save]

Options:
  -h --help            Show help
  -w, --wallet PATH    Use a particular wallet file (e.g. `-w ./wallet2.dat`)
  -n, --node HOSTNAME  The hostname of node to use for RPC (default: localhost)
  -p, --port PORT      Port node is listening on (default: 9999)
"""
from __future__ import print_function

import json

from docopt import docopt

from luracoin.exceptions import WalletAlreadyExistError
from luracoin.wallet import create_wallet, generate_wallet


def main(args):  # type: ignore
    if args["generateWallet"]:
        generateWallet(save=args["--save"])


def generateWallet(save):  # type: ignore
    if save:
        try:
            wallet = create_wallet()
        except WalletAlreadyExistError:
            wallet = {"message": "Wallet already exist"}
    else:
        wallet = generate_wallet()

    print(json.dumps(wallet, indent=4))


if __name__ == "__main__":
    main(docopt(__doc__, version="luracoin client 0.1"))  # type: ignore
