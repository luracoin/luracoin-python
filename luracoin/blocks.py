import json
import msgpack
import redis
import binascii
#import plyvel
from pymongo import MongoClient
from typing import Any
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import sha256d, bits_to_target
from luracoin.transactions import Transaction
from luracoin.chain import get_value

class Block:
    def __init__(
        self,
        version: int = None,
        height: int = None,
        prev_block_hash: str = None,
        bits: int = None,
        nonce: int = None,
        timestamp: int = None,
        txns: list = [],
    ) -> None:
        self.height = height
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
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
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

    """
    def serialize(self, to_json=True) -> bytes:
        return msgpack.packb(self.json(), use_bin_type=True)
    """

    def serialize(self) -> bytes:
        version_bytes = self.version.to_bytes(4, byteorder="little", signed=False)
        id_bytes = binascii.a2b_hex(self.id)
        height_bytes = self.height.to_bytes(4, byteorder="little", signed=False)
        prev_block_hash_bytes = binascii.a2b_hex(self.prev_block_hash)
        timestamp_bytes = self.timestamp.to_bytes(4, byteorder="big", signed=False)
        bits_bytes = self.bits
        nonce_bytes = self.nonce.to_bytes(4, byteorder="little", signed=False)


        print("=======")
        print("Serialize: ")
        print(Config.MAGIC_BYTES)
        print(version_bytes)
        print(id_bytes)
        print(height_bytes)
        print(prev_block_hash_bytes)
        print(timestamp_bytes)
        print(bits_bytes)
        print(nonce_bytes)
        print("=======")

    def deserialize(self, block_serialized: str) -> None:
        pass

    def is_valid_proof(self) -> bool:
        target = bits_to_target(self.bits)
        if self.id.startswith("0000"):
            print(f"FUNCION is_valid_proof <{self.bits}> <{target}>")
            print(self.id)
            print(int(self.id, 16))
            print(int(bits_to_target(self.bits), 16))
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
        7) [ ] Block Height
        """
        current_height = get_value("height")
        if not current_height:
            current_height = -1

        if not self.is_valid_proof():
            print("Proof of work is invalid")
            return False
        
        if self.block.height != current_height + 1:
            print("Block height is invalid")
            return False

        return True

    def save(self) -> None:
        print("=======")
        print(json.dumps(self.json(), indent=4))
        print(self.serialize())
        print("=======")
        if self.validate():
            print("Block is valid")

    def create(self, propagate: bool = True) -> None:
        pass
