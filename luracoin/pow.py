def proof_of_work(block: "Block", starting_at=0) -> int:  # type: ignore
    """
    Simple Proof of Work Algorithm
    """
    block.nonce = starting_at
    stop_loop = block.is_valid_proof()

    while not stop_loop:
        block.nonce = block.nonce + 1
        stop_loop = block.is_valid_proof()

    return block.nonce
