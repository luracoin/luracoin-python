"""
Luracoin CLI

Usage:
  luracoin generateWallet
  luracoin mine --address=<address> [--port=<port>]
  luracoin getBalance <address>
  luracoin getBlock <height>
  luracoin getInfo

Options:
  -h --help            Show help
  --port=<port>        P2P listening port [default: 9999]
"""
import asyncio
import json

from docopt import docopt

from luracoin import __version__
from luracoin.wallet import generate_wallet


def cli() -> None:
    """Entry point registered as the `luracoin` console script."""
    args = docopt(__doc__, version=f"luracoin {__version__}")
    main(args)


def main(args):
    if args["generateWallet"]:
        generateWallet()
    elif args["mine"]:
        port = int(args["--port"] or 9999)
        mine(args["--address"], port)
    elif args["getBalance"]:
        get_balance(args["<address>"])
    elif args["getBlock"]:
        get_block(int(args["<height>"]))
    elif args["getInfo"]:
        get_info()


def mine(address, port=9999):
    from luracoin.network.miner import MiningNode

    node = MiningNode(address=address, port=port)
    print(f"Starting mining node on port {port} with address {address}")
    asyncio.run(node.start())


def generateWallet():
    wallet = generate_wallet()
    print(json.dumps(wallet, indent=4))


def get_balance(address):
    from luracoin.chain import Chain

    chain = Chain()
    account = chain.get_account(address)
    if account:
        print(json.dumps(account, indent=4))
    else:
        print(json.dumps({"balance": 0, "nonce": 0}, indent=4))


def get_block(height):
    from luracoin.blocks import Block

    block = Block.get(height)
    if block:
        print(json.dumps(block.json(), indent=4))
    else:
        print(f"Block {height} not found.")


def get_info():
    from luracoin.chain import Chain
    from luracoin.config import Config

    chain = Chain()
    info = {
        "height": chain.tip,
        "difficulty": Config.STARTING_DIFFICULTY.hex(),
    }
    print(json.dumps(info, indent=4))


if __name__ == "__main__":
    cli()
