import threading
from luracoin.blocks import Block
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.pow import proof_of_work
from tests.constants import WALLET_1


def _make_block(bits=b"\x1f\x00\xff\xff"):
    coinbase = Transaction(
        chain=1, nonce=0, fee=0, value=50000,
        from_address="0" * 34, to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    return Block(
        version=1, height=0, miner=WALLET_1["address"],
        prev_block_hash="0" * 64, timestamp=1_623_168_442,
        bits=bits, nonce=0, txns=[coinbase],
    )


def test_pow_without_stop_event_works():
    block = _make_block()
    nonce = proof_of_work(block)
    assert nonce >= 0
    assert block.is_valid_proof()


def test_pow_with_stop_event_not_set_works():
    block = _make_block()
    event = threading.Event()
    nonce = proof_of_work(block, stop_event=event)
    assert nonce >= 0
    assert block.is_valid_proof()


def test_pow_interrupted_returns_minus_one():
    # Use hard difficulty so it takes many iterations
    block = _make_block(bits=b"\x1d\x00\xff\xff")
    event = threading.Event()
    event.set()  # Set immediately so it stops at first check

    nonce = proof_of_work(block, stop_event=event)
    assert nonce == -1


def test_pow_stop_event_set_during_mining():
    """Start mining, set stop after a short delay, verify interruption."""
    block = _make_block(bits=b"\x14\x00\xff\xff")  # Hard difficulty
    event = threading.Event()

    def set_after_delay():
        # Set event after a tiny delay
        import time
        time.sleep(0.01)
        event.set()

    timer = threading.Thread(target=set_after_delay)
    timer.start()

    nonce = proof_of_work(block, stop_event=event)
    timer.join()

    assert nonce == -1
