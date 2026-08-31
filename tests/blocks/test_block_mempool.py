from binascii import unhexlify
from unittest.mock import patch, MagicMock

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.transactions import Transaction
from luracoin.config import Config
from tests.constants import WALLET_1, WALLET_2, WALLET_3


def _make_serialized_tx(wallet, nonce, fee, value):
    recipient = (
        WALLET_1["address"]
        if wallet["address"] != WALLET_1["address"]
        else WALLET_2["address"]
    )
    tx = Transaction(
        chain=Config.CHAIN_ID,
        nonce=nonce,
        fee=fee,
        value=value,
        from_address=wallet["address"],
        to_address=recipient,
    )
    return tx.sign(unhexlify(wallet["private_key"])).serialize()


def test_select_transactions_sorts_by_fee_descending():
    """select_transactions should pick transactions sorted by fee (highest first)."""
    chain = Chain()
    for wallet in (WALLET_1, WALLET_2, WALLET_3):
        chain.set_account(
            wallet["address"], {"balance": 1_000_000, "nonce": 0}
        )

    # Independent senders keep fee ordering independent from nonce ordering.
    tx_low = _make_serialized_tx(WALLET_1, nonce=1, fee=100, value=1000)
    tx_high = _make_serialized_tx(
        WALLET_2, nonce=1, fee=9999, value=2000
    )
    tx_mid = _make_serialized_tx(
        WALLET_3, nonce=1, fee=5000, value=3000
    )

    mock_redis = MagicMock()
    mock_redis.keys.return_value = [b"tx1", b"tx2", b"tx3"]
    mock_redis.get.side_effect = [tx_low, tx_high, tx_mid]

    with patch("luracoin.blocks.redis.Redis", return_value=mock_redis):
        block = Block(height=0, miner=WALLET_1["address"])
        block.select_transactions()

    assert len(block.txns) == 3
    assert block.txns[0].fee == 9999
    assert block.txns[1].fee == 5000
    assert block.txns[2].fee == 100


def test_select_transactions_respects_max_block_size():
    """select_transactions should not exceed max block size."""
    # At height 0, max_block_size = 10_000, header = 118
    # Available = 10_000 - 118 = 9_882 bytes
    # Each tx = 213 bytes => max ~46 txns
    Chain().set_account(
        WALLET_1["address"], {"balance": 1_000_000, "nonce": 0}
    )
    serialized_txns = [
        _make_serialized_tx(
            WALLET_1, nonce=i + 1, fee=100, value=1000 + i
        )
        for i in range(50)
    ]

    mock_redis = MagicMock()
    mock_redis.keys.return_value = [f"tx{i}".encode() for i in range(50)]
    mock_redis.get.side_effect = serialized_txns

    with patch("luracoin.blocks.redis.Redis", return_value=mock_redis):
        block = Block(height=0, miner=WALLET_1["address"])
        block.select_transactions()

    # Should have selected fewer than 50 txns due to size limit
    assert len(block.txns) < 50
    total_size = len(block.txns) * Config.TRANSACTION_LENGTH
    from luracoin.chain import max_block_size
    assert total_size <= max_block_size(0) - 118


def test_select_transactions_empty_mempool():
    """select_transactions with empty mempool yields no transactions."""
    mock_redis = MagicMock()
    mock_redis.keys.return_value = []

    with patch("luracoin.blocks.redis.Redis", return_value=mock_redis):
        block = Block(height=0, miner=WALLET_1["address"])
        block.select_transactions()

    assert block.txns == []


def test_clean_mempool_deletes_transaction_ids():
    """clean_mempool should delete each transaction's id from Redis."""
    tx1 = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=50000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    tx2 = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=100,
        value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    ).sign(unhexlify(WALLET_2["private_key"]))

    mock_redis = MagicMock()

    with patch("luracoin.blocks.redis.Redis", return_value=mock_redis):
        block = Block(
            version=1, height=0, miner=WALLET_1["address"],
            prev_block_hash="0" * 64, timestamp=1_623_168_442,
            bits=b"\x1f\x00\xff\xff", nonce=0,
            txns=[tx1, tx2],
        )
        block.clean_mempool()

    # Coinbase transactions were never admitted to the mempool.
    mock_redis.delete.assert_called_once_with(tx2.id, tx2.mempool_nonce_key)


def test_clean_mempool_handles_connection_error():
    """clean_mempool should not raise if Redis is down."""
    import redis as redis_lib

    tx = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=100,
        value=1000,
        from_address=WALLET_2["address"],
        to_address=WALLET_1["address"],
    ).sign(unhexlify(WALLET_2["private_key"]))

    mock_redis = MagicMock()
    mock_redis.delete.side_effect = redis_lib.exceptions.ConnectionError("down")

    with patch("luracoin.blocks.redis.Redis", return_value=mock_redis):
        block = Block(
            version=1, height=0, miner=WALLET_1["address"],
            prev_block_hash="0" * 64, timestamp=1_623_168_442,
            bits=b"\x1f\x00\xff\xff", nonce=0,
            txns=[tx],
        )
        # Should not raise
        block.clean_mempool()
