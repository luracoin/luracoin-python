import safer
import json
import redis
import binascii

from typing import Any
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import sha256d, bits_to_target, mining_reward
from luracoin.transactions import Transaction
from luracoin.chain import Chain, blk_file_format, get_current_blk_file

class Block(Chain):
    def __init__(
        self,
        version: int = None,
        height: int = None,
        miner: str = None,
        prev_block_hash: str = None,
        bits: int = None,
        nonce: int = None,
        timestamp: int = None,
        txns: list = None,
    ) -> None:
        self.height = height
        self.miner = miner
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.txns = txns or []

    @property
    def id(self) -> str:
        txns_ids = "".join(map(lambda t: t.id, self.txns))

        string_to_hash = (
            str(self.height)
            + str(self.miner)
            + str(self.version)
            + str(self.prev_block_hash)
            + str(self.timestamp)
            + str(self.bits.hex())
            + str(self.nonce)
            + str(txns_ids)
        )

        block_id = sha256d(string_to_hash)
        return block_id

    def header(self) -> Any:
        """
        Block header
        """
        header = {
            "height": self.height,
            "prev_block_hash": self.prev_block_hash,
            "miner": self.miner,
            "id": self.id,
            "nonce": self.nonce,
            "version": self.version,
            "timestamp": self.timestamp,
            "bits": self.bits.hex(),
        }

        return header

    def json(self) -> dict:
        block = self.header()
        block["txns"] = []

        for tx in self.txns:
            block["txns"].append(tx.json())

        return block

    def select_transactions(self) -> "Block":
        redis_client = redis.Redis(
            host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
        )
        keys = redis_client.keys()
        transactions = []

        for key in keys:
            serialized_tx = redis_client.get(key)
            txn = Transaction()
            txn.deserialize(serialized_tx)
            transactions.append(txn)

        # Sort by fee descending
        transactions.sort(key=lambda t: t.fee, reverse=True)

        # Limit to max block size
        from luracoin.chain import max_block_size
        header_size = 118
        max_size = max_block_size(self.height or 0) - header_size
        selected = []
        current_size = 0
        for txn in transactions:
            tx_size = Config.TRANSACTION_LENGTH
            if current_size + tx_size > max_size:
                break
            selected.append(txn)
            current_size += tx_size

        self.txns = selected
        return self

    def clean_mempool(self) -> None:
        """Remove included transactions from Redis mempool."""
        try:
            redis_client = redis.Redis(
                host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
            )
            for txn in self.txns:
                redis_client.delete(txn.id)
        except redis.exceptions.ConnectionError:
            pass

    def serialize(self) -> bytes:
        version_bytes = self.version.to_bytes(
            4, byteorder="little", signed=False
        )
        id_bytes = binascii.a2b_hex(self.id)
        miner_bytes = str.encode(self.miner)
        prev_block_hash_bytes = binascii.a2b_hex(self.prev_block_hash)
        height_bytes = self.height.to_bytes(
            4, byteorder="little", signed=False
        )
        timestamp_bytes = self.timestamp.to_bytes(
            4, byteorder="big", signed=False
        )
        bits_bytes = self.bits
        nonce_bytes = self.nonce.to_bytes(4, byteorder="little", signed=False)

        transaction_bytes = b""
        for txn in self.txns:
            transaction_bytes += txn.serialize()

        return (
            version_bytes
            + id_bytes
            + prev_block_hash_bytes
            + height_bytes
            + miner_bytes
            + timestamp_bytes
            + bits_bytes
            + nonce_bytes
            + transaction_bytes
        )

    def deserialize(self, block_serialized: bytes) -> "Block":
        self.version = int.from_bytes(
            block_serialized[0:4], byteorder="little"
        )
        self.prev_block_hash = block_serialized[36:68].hex()
        self.height = int.from_bytes(
            block_serialized[68:72], byteorder="little"
        )
        self.miner = block_serialized[72:106].decode("utf-8")
        self.timestamp = int.from_bytes(
            block_serialized[106:110], byteorder="big"
        )
        self.bits = block_serialized[110:114]
        self.nonce = int.from_bytes(
            block_serialized[114:118], byteorder="little"
        )

        self.txns = []
        block_transations = block_serialized[118:]

        for i in range(0, len(block_transations), Config.TRANSACTION_LENGTH):
            txn = Transaction()
            txn.deserialize(block_transations[i : i + Config.TRANSACTION_LENGTH])
            self.txns.append(txn)
        return self

    def is_valid_proof(self) -> bool:
        target = bits_to_target(self.bits)
        return int(self.id, 16) <= int(target, 16)

    def validate(self) -> bool:
        if not self.is_valid_proof():
            return False

        # Block size
        from luracoin.chain import max_block_size
        if len(self.serialize()) > max_block_size(self.height):
            return False

        # Timestamp: not too far in the future
        import time
        if self.timestamp > int(time.time()) + Config.MAX_FUTURE_BLOCK_TIME:
            return False

        # Timestamp and height vs previous block
        if self.height > 0:
            prev_block = Block.get(self.height - 1)
            if prev_block:
                if self.timestamp <= prev_block.timestamp:
                    return False
                if self.height != prev_block.height + 1:
                    return False

        # Validate transactions
        for txn in self.txns:
            if not txn.validate():
                return False

        # Coin supply: coinbase value <= mining_reward + sum(fees)
        total_fees = sum(txn.fee for txn in self.txns if not txn.is_coinbase)
        coinbase_txns = [txn for txn in self.txns if txn.is_coinbase]
        if coinbase_txns:
            coinbase_value = sum(txn.value for txn in coinbase_txns)
            if coinbase_value > mining_reward(self.height) + total_fees:
                return False

        return True

    @classmethod
    def get_blocks_from_file(cls, fileNumber):
        """
        Get all blocks from a file
        """
        obj = cls.__new__(cls)
        block_file = f"{Config.BLOCKS_DIR}blk{blk_file_format(fileNumber)}.dat"
        blocks = []

        with safer.open(block_file, "rb") as f:
            file_bytes = f.read()
            while file_bytes:
                block_size = int.from_bytes(file_bytes[:4], byteorder="little", signed=False)
                blocks.append(obj.deserialize(file_bytes[4:block_size + 4]))
                file_bytes = file_bytes[4+block_size:]

        return blocks

    @classmethod
    def last(cls):
        """
        Return the last block
        """
        obj = cls.__new__(cls)
        return cls.get(obj.tip)

    @classmethod
    def get(cls, height):
        """
        Get a block by height
        """
        obj = cls.__new__(cls)
        block_file_number = obj.get_block_file_number(height)
        if block_file_number is None:
            return None

        blocks_in_file = obj.get_blocks_from_file(block_file_number)
        for block in blocks_in_file:
            if block.height == height:
                return block

        return None


    def save(self) -> None:
        file_number = self.current_file_number
        current_block_file = f"{Config.BLOCKS_DIR}{get_current_blk_file(self.current_file_number)}"

        with safer.open(current_block_file, "ab") as w:
            serialized_block = self.serialize()
            block_size = len(serialized_block)
            w.write(block_size.to_bytes(4, byteorder="little", signed=False) + serialized_block)

        self.set_tip(self.height)
        self.set_block_file_number(self.height, file_number)

        # Save each transaction and update balances
        for i, txn in enumerate(self.txns):
            txn.save(block_height=self.height, tx_index=i)

        # Credit mining reward to miner
        self.credit_account(self.miner, mining_reward(self.height))

        # Clean mempool
        self.clean_mempool()

    def create(self) -> "Block":
        from luracoin.pow import proof_of_work
        import time

        prev_block = Block.get(self.tip)
        self.height = self.tip + 1 if prev_block else 0
        self.prev_block_hash = prev_block.id if prev_block else "0" * 64
        self.version = 1
        self.timestamp = int(time.time())
        self.bits = Config.STARTING_DIFFICULTY

        # Coinbase transaction
        total_fees = sum(txn.fee for txn in self.txns)
        coinbase = Transaction(
            chain=0,
            nonce=0,
            fee=0,
            value=mining_reward(self.height) + total_fees,
            from_address="0" * 34,
            to_address=self.miner,
            unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
        )
        self.txns.insert(0, coinbase)

        self.nonce = 0
        proof_of_work(self)
        self.save()
        return self
