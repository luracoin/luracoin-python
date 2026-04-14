def proof_of_work(block: "Block", starting_at=0, stop_event=None) -> int:  # type: ignore
    """
    Simple Proof of Work Algorithm.

    If stop_event (threading.Event) is provided, checks it every 1000
    iterations so mining can be interrupted when a new block arrives
    from a peer. Returns -1 if interrupted.
    """
    block.nonce = starting_at

    while not block.is_valid_proof():
        if stop_event and block.nonce % 1000 == 0 and stop_event.is_set():
            return -1
        block.nonce += 1

    return block.nonce
