from binascii import unhexlify
from luracoin.transactions import Transaction
from luracoin.config import Config
from luracoin.chain import Chain, set_value, get_value
from tests.constants import WALLET_1, WALLET_2, WALLET_3


def test_save_coinbase_credits_to_address():
    """Coinbase transaction adds value to to_address balance."""
    chain = Chain()

    # No account exists yet
    assert chain.get_account(WALLET_1["address"]) is None

    tx = Transaction(
        chain=1, nonce=0, fee=0, value=5_000_000_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    tx.save(block_height=0)

    account = chain.get_account(WALLET_1["address"])
    assert account is not None
    assert account["balance"] == 5_000_000_000


def test_save_coinbase_does_not_debit_from_address():
    """Coinbase from_address is zeros -- no account should be debited."""
    chain = Chain()

    tx = Transaction(
        chain=1, nonce=0, fee=0, value=5_000_000_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    tx.save(block_height=0)

    # The zeros address should NOT have an account
    assert chain.get_account("0" * 34) is None


def test_save_regular_tx_updates_both_balances():
    """Regular transaction debits sender and credits receiver."""
    chain = Chain()

    # Give WALLET_1 some initial balance
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=1_000, value=3_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))
    tx.save(block_height=1)

    sender = chain.get_account(WALLET_1["address"])
    receiver = chain.get_account(WALLET_2["address"])

    # Sender loses value + fee
    assert sender["balance"] == 10_000_000 - 3_000_000 - 1_000
    # Receiver gains value (not fee)
    assert receiver["balance"] == 3_000_000


def test_save_regular_tx_increments_sender_nonce():
    """Sender's nonce is incremented after saving."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))
    tx.save(block_height=1)

    assert chain.get_account(WALLET_1["address"])["nonce"] == 1


def test_save_credits_existing_receiver_account():
    """If receiver already has a balance, value is added to it."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})
    chain.set_account(WALLET_2["address"], {"balance": 500_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=2_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))
    tx.save(block_height=1)

    assert chain.get_account(WALLET_2["address"])["balance"] == 2_500_000


def test_save_stores_tx_record_in_chainstate():
    """Transaction is indexed by hash in the chainstate database."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 10_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=1_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))
    tx.save(block_height=5, tx_index=3)

    # Check tx record exists: key = 't' + tx_hash
    key = b"t" + tx.id.encode()
    raw = get_value(Config.DATABASE_CHAINSTATE, key)
    assert raw is not None

    # First 4 bytes = block height, next 2 bytes = tx index
    stored_height = int.from_bytes(raw[0:4], byteorder="little")
    stored_index = int.from_bytes(raw[4:6], byteorder="little")
    assert stored_height == 5
    assert stored_index == 3
