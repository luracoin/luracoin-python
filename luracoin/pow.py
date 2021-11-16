def proof_of_work(block) -> int:  # type: ignore
    """
    Simple Proof of Work Algorithm
    """
    stop_loop = False
    while stop_loop is False:
        block.nonce = block.nonce + 1
        stop_loop = block.is_valid_proof()

    return block.nonce
