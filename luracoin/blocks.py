import safer
import json
import redis
import binascii
import rocksdb

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
        txns: list = [],
    ) -> None:
        self.height = height
        self.miner = miner
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.txns = txns

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

        for key in sorted(keys):
            serialized_tx = redis_client.get(key)
            txn = Transaction()
            txn.deserialize(serialized_tx.hex())
            transactions.append(txn)

        self.txns = transactions
        return self

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

        """
        print("\n----------")
        print(f"magic bytes: {Config.MAGIC_BYTES.hex()}")
        print(f"version_bytes: {version_bytes.hex()}")
        print(f"id_bytes: {id_bytes.hex()}")
        print(f"prev_block_hash_bytes: {prev_block_hash_bytes.hex()}")
        print(f"miner_bytes: {miner_bytes.hex()}")
        print(f"height_bytes: {height_bytes.hex()}")
        print(f"timestamp_bytes: {timestamp_bytes.hex()}")
        print(f"bits_bytes: {bits_bytes.hex()}")
        print(f"nonce_bytes: {nonce_bytes.hex()}")
        print("----------\n")
        """

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

        for i in range(0, len(block_transations), 179):
            txn = Transaction()
            txn.deserialize(block_transations[i : i + 179])
            self.txns.append(txn)
        return self

    def is_valid_proof(self) -> bool:
        target = bits_to_target(self.bits)
        if self.id.startswith("00000"):
            print(f"{int(self.id, 16)} <= {int(target, 16)}")
        return int(self.id, 16) <= int(target, 16)

    def validate(self) -> bool:
        """
        Validate:
        1) [X] POW
        2) [ ] Coins supply
        3) [ ] Transactions
        4) [ ] Block Size
        5) [ ] Reward + Fees
        6) [ ] Timestamp
        7) [X] Block Height
        """
        if not self.is_valid_proof():
            print("Proof of work is invalid")
            return False

        for txn in self.txns:
            if not txn.validate():
                print("Transaction is invalid")
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
        return obj.get_block(obj.last_height)

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
        """
        if not self.validate():
            raise BlockNotValidError("Block is not valid")
        """
        file_number = self.current_file_number
        current_block_file = f"{Config.BLOCKS_DIR}{get_current_blk_file(self.current_file_number)}"

        with safer.open(current_block_file, "ab") as w:
            serialized_block = self.serialize()
            block_size = len(serialized_block)
            w.write(block_size.to_bytes(4, byteorder="little", signed=False) + serialized_block)

        print(Block.get_blocks_from_file(0))
        self.set_height(self.height)
        self.set_block_file_number(self.height, file_number)

        miner_balance = self.get_account(self.miner)
        miner_reward = mining_reward(self.height)
        print(f"Miner reward: {miner_reward}")
        
        # TODO: Update balances
        # TODO: Update stacking
        # TODO: Update difficulty

    def create(self, propagate: bool = True) -> None:
        pass
