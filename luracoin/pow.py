import hashlib
import time
from luracoin.helpers import sha256d
import json


def proof_of_work(block, difficulty):
    """
    Simple Proof of Work Algorithm
    """
    stop_loop = False
    while stop_loop is False:
        block.nonce = block.nonce + 1
        stop_loop = valid_proof(block.generate_hash(), difficulty)

    print(json.dumps(block.json()))
    return block.nonce

def valid_proof(block_hash, difficulty):
    """
    Validates the Proof
    :param block_hash: Block hash
    :param difficulty: Number of 0's
    :return: True if correct, False if not.
    """
    target = "".join(["0" for d in range(difficulty)])
    return block_hash[:difficulty] == target

def validate_pow(block):
    return True
