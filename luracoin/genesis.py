from luracoin.config import Config
from luracoin.transactions import Transaction
from luracoin.helpers import mining_reward


# Owner address - replace with your own address
GENESIS_ADDRESS = "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"

GENESIS_TIMESTAMP = 1_623_168_442


def build_genesis_block():
    """Build the genesis block (height 0)."""
    from luracoin.blocks import Block

    coinbase = Transaction(
        chain=0,
        nonce=0,
        fee=0,
        value=Config.COINS_TO_FORGE,
        from_address="0" * 34,
        to_address=GENESIS_ADDRESS,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    block = Block(
        version=1,
        height=0,
        miner=GENESIS_ADDRESS,
        prev_block_hash="0" * 64,
        timestamp=GENESIS_TIMESTAMP,
        bits=Config.STARTING_DIFFICULTY,
        nonce=0,
        txns=[coinbase],
    )

    return block


def initialize_chain():
    """Save genesis block if chain is empty."""
    from luracoin.chain import Chain

    chain = Chain()
    if chain.tip == 0 and chain.get_block_file_number(0) is None:
        genesis = build_genesis_block()
        genesis.save()
