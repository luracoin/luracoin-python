from luracoin.helpers import bits_to_target


def proof_of_work(block) -> int:  # type: ignore
    """
    Simple Proof of Work Algorithm
    """
    stop_loop = False
    while stop_loop is False:
        block.nonce = block.nonce + 1
        stop_loop = valid_proof(block.id, block.bits)

    return block.nonce


def valid_proof(block_hash: str, difficulty: str) -> bool:
    """
    Validates the Proof
    :param block_hash: Block hash
    :param difficulty: Number of 0's
    :return: True if correct, False if not.
    """
    return int(block_hash, 16) <= int(bits_to_target(difficulty), 16)
