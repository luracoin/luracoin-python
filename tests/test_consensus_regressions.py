import hashlib
import json
from binascii import unhexlify
from pathlib import Path
from unittest.mock import patch

import pytest

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.genesis import (
    GENESIS_MANIFESTS,
    build_genesis_block,
    initialize_chain,
)
from luracoin.helpers import calculate_new_bits, mining_reward
from luracoin.transactions import (
    SECP256K1_ORDER,
    Transaction,
    is_valid_unlocking_script,
)
from luracoin.wallet import is_valid_address
from tests.constants import WALLET_1, WALLET_2, WALLET_3


class _FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        if isinstance(key, bytes):
            key = key.decode()
        return self.values.get(key)

    def keys(self):
        return [key.encode() for key in self.values]

    def eval(self, _script, _key_count, nonce_key, tx_key, tx_id, raw):
        claimed = self.values.get(nonce_key)
        if claimed is not None and claimed != tx_id:
            return 0
        self.values[nonce_key] = tx_id
        self.values[tx_key] = raw
        return 1


def _signed_tx(nonce, value, fee=0, recipient=WALLET_2["address"]):
    return Transaction(
        chain=Config.CHAIN_ID,
        nonce=nonce,
        fee=fee,
        value=value,
        from_address=WALLET_1["address"],
        to_address=recipient,
    ).sign(unhexlify(WALLET_1["private_key"]))


def _next_block(genesis, transactions, miner=WALLET_3["address"]):
    fees = sum(transaction.fee for transaction in transactions)
    coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=1,
        fee=0,
        value=mining_reward(1) + fees,
        from_address="0" * 34,
        to_address=miner,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    return Block(
        version=1,
        height=1,
        miner=miner,
        prev_block_hash=genesis.id,
        timestamp=genesis.timestamp + 1,
        bits=genesis.bits,
        nonce=0,
        txns=[coinbase] + transactions,
    )


def test_genesis_manifest_is_valid_and_mainnet_fails_closed(monkeypatch):
    genesis = build_genesis_block()
    manifest = GENESIS_MANIFESTS[Config.NETWORK]
    assert genesis.id == manifest["id"]
    assert genesis.is_valid_proof()
    assert genesis.validate()

    monkeypatch.setattr(Config, "NETWORK", "mainnet")
    monkeypatch.setattr(Config, "CHAIN_ID", 0)
    with pytest.raises(BlockNotValidError, match="Mainnet genesis"):
        build_genesis_block()


def test_contextual_transition_and_retry_do_not_double_reward(monkeypatch):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    genesis = initialize_chain()
    transaction = _signed_tx(nonce=1, value=123_000, fee=2_000)
    block = _next_block(genesis, [transaction])

    assert block.validate()
    block.save()
    chain = Chain()
    assert chain.get_account(WALLET_1["address"]) == {
        "balance": Config.COINS_TO_FORGE - 125_000,
        "nonce": 1,
    }
    assert chain.get_account(WALLET_2["address"])["balance"] == 123_000
    assert chain.get_account(WALLET_3["address"])["balance"] == (
        mining_reward(1) + 2_000
    )

    balances = {
        wallet: dict(chain.get_account(wallet))
        for wallet in (
            WALLET_1["address"],
            WALLET_2["address"],
            WALLET_3["address"],
        )
    }
    block.save()
    assert all(
        chain.get_account(wallet) == value
        for wallet, value in balances.items()
    )
    blocks = Block.get_blocks_from_file(0)
    assert len(blocks) == 2
    assert blocks[0] is not blocks[1]
    assert [candidate.height for candidate in blocks] == [0, 1]


def test_same_block_duplicate_nonce_and_aggregate_overspend_are_rejected(
    monkeypatch,
):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    genesis = initialize_chain()

    duplicate_nonce = _next_block(
        genesis,
        [_signed_tx(1, 10), _signed_tx(1, 11)],
    )
    assert duplicate_nonce.validate() is False

    overspend = _next_block(
        genesis,
        [
            _signed_tx(1, Config.COINS_TO_FORGE // 2 + 1),
            _signed_tx(2, Config.COINS_TO_FORGE // 2 + 1),
        ],
    )
    assert overspend.validate() is False


def test_coinbase_link_and_difficulty_rules_are_exact(monkeypatch):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    genesis = initialize_chain()
    valid = _next_block(genesis, [])
    assert valid.validate()

    valid.prev_block_hash = "f" * 64
    assert valid.validate() is False
    valid.prev_block_hash = genesis.id

    valid.bits = b"\x1f\x00\xff\xff"
    assert valid.validate() is False
    valid.bits = genesis.bits

    second_coinbase = Transaction(
        chain=Config.CHAIN_ID,
        nonce=0,
        fee=0,
        value=1,
        from_address="0" * 34,
        to_address=valid.miner,
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    valid.txns.append(second_coinbase)
    assert valid.validate() is False


def test_interrupted_save_recovers_without_duplicate_file_or_state(
    monkeypatch,
):
    monkeypatch.setattr(Block, "is_valid_proof", lambda _block: True)
    genesis = initialize_chain()
    block = _next_block(genesis, [])
    original_apply = Chain.apply_account_updates

    def interrupt_after_append(*_args, **_kwargs):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(Block, "apply_account_updates", interrupt_after_append)
    with pytest.raises(RuntimeError, match="simulated crash"):
        block.save()
    assert len(Block.get_blocks_from_file(0)) == 2
    assert Chain().get_account(WALLET_3["address"]) is None

    monkeypatch.setattr(Block, "apply_account_updates", original_apply)
    block.save()
    assert len(Block.get_blocks_from_file(0)) == 2
    assert Chain().get_account(WALLET_3["address"])[
        "balance"
    ] == mining_reward(1)


def test_reward_halving_boundaries_and_tail_floor():
    halving = Config.HALVING_BLOCKS
    assert mining_reward(0) == Config.BLOCK_REWARD
    assert mining_reward(halving - 1) == Config.BLOCK_REWARD
    assert mining_reward(halving) == Config.BLOCK_REWARD // 2
    assert mining_reward(5 * halving) == Config.BLOCK_REWARD // 32
    assert mining_reward(6 * halving) == Config.TAIL_REWARD
    assert mining_reward(100 * halving) == Config.TAIL_REWARD


def test_signature_and_hash_interoperability_vector():
    vector_path = Path(__file__).parents[1] / "vectors.json"
    vector = json.loads(vector_path.read_text())["transaction_v1"]
    unsigned = bytes.fromhex(vector["unsigned_hex"])
    assert len(unsigned) == 85
    assert (
        hashlib.sha256(unsigned).hexdigest()
        == vector["signing_digest_sha256_hex"]
    )

    transaction = Transaction().deserialize(unsigned)
    transaction.sign(bytes.fromhex(vector["private_key_hex"]))
    assert transaction.unlock_sig.hex() == vector["unlock_sig_hex"]
    assert len(transaction.unlock_sig) == 128
    assert transaction.serialize().hex() == vector["raw_hex"]
    assert len(transaction.serialize()) == Config.TRANSACTION_LENGTH == 213
    assert transaction.id == vector["txid"]

    signature_s = int.from_bytes(transaction.unlock_sig[96:], byteorder="big")
    assert signature_s <= SECP256K1_ORDER // 2

    high_s_unlock = transaction.unlock_sig[:96] + (
        SECP256K1_ORDER - signature_s
    ).to_bytes(32, byteorder="big")
    assert not is_valid_unlocking_script(
        high_s_unlock,
        unsigned,
        vector["from_address"],
    )


def test_addresses_require_luracoin_base58check_version():
    assert is_valid_address(WALLET_1["address"])
    assert not is_valid_address("1H7NtUENrEbwSVm52fHePzBnu4W3bCqimP")
    assert not is_valid_address("L" * 34)


def test_mempool_atomically_reserves_nonce_and_accepts_contiguous_sequence():
    Chain().set_account(WALLET_1["address"], {"balance": 10_000, "nonce": 0})
    redis_client = _FakeRedis()
    first = _signed_tx(1, 1_000, fee=10)
    second = _signed_tx(2, 2_000, fee=20)
    conflict = _signed_tx(1, 999, fee=99)

    with patch("luracoin.transactions.redis.Redis", return_value=redis_client):
        assert first.to_transaction_pool()
        assert second.to_transaction_pool()
        assert conflict.to_transaction_pool() is False

    assert redis_client.get(first.mempool_nonce_key) == first.id
    assert redis_client.get(second.mempool_nonce_key) == second.id


def test_template_selection_simulates_pending_nonce_and_balance():
    Chain().set_account(WALLET_1["address"], {"balance": 10_000, "nonce": 0})
    redis_client = _FakeRedis()
    first = _signed_tx(1, 1_000, fee=10)
    second = _signed_tx(2, 2_000, fee=200)
    redis_client.values[first.id] = first.serialize()
    redis_client.values[second.id] = second.serialize()
    redis_client.values[first.mempool_nonce_key] = first.id
    redis_client.values[second.mempool_nonce_key] = second.id

    with patch("luracoin.blocks.redis.Redis", return_value=redis_client):
        block = Block(
            height=1, miner=WALLET_3["address"]
        ).select_transactions()

    # Fee sorting sees nonce 2 first; contextual selection waits for nonce 1.
    assert [transaction.nonce for transaction in block.txns] == [1, 2]


def test_block_file_rotation_skips_multiple_full_files(monkeypatch):
    Config.ensure_data_dirs()
    monkeypatch.setattr(Config, "MAX_FILE_SIZE", 10)
    blocks_dir = Path(Config.BLOCKS_DIR)
    (blocks_dir / "blk000000.dat").write_bytes(b"0" * 10)
    (blocks_dir / "blk000001.dat").write_bytes(b"1" * 10)

    chain = Chain()
    chain.set_current_file_number(0)
    assert chain.current_file_number == 2

    (blocks_dir / "blk000002.dat").write_bytes(b"2" * 5)
    # Five payload bytes plus the four-byte record prefix do not fit.
    assert chain.file_number_for_block(5) == 3


def test_expected_bits_retargets_from_exact_history_and_fails_closed(
    monkeypatch,
):
    interval = Config.DIFFICULTY_ADJUSTMENT_INTERVAL
    previous = type(
        "Previous",
        (),
        {"bits": Config.STARTING_DIFFICULTY, "timestamp": 100_000},
    )()
    first = type("First", (), {"timestamp": 10_000})()
    history = {interval - 1: previous, 0: first}
    monkeypatch.setattr(
        Block,
        "get",
        classmethod(lambda _cls, height: history.get(height)),
    )

    expected = calculate_new_bits(
        previous.bits,
        previous.timestamp - first.timestamp,
        interval * Config.BLOCK_TIME,
    )
    assert Block.expected_bits(interval) == expected

    history.pop(0)
    with pytest.raises(BlockNotValidError, match="missing"):
        Block.expected_bits(interval)
