import msgpack
#import plyvel
from pymongo import MongoClient
from typing import Any
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import (
    sha256d,
    bits_to_target,
)
from luracoin.transactions import Transaction
from luracoin.chain import main

class Block:
    def __init__(
        self,
        version: int = None,
        prev_block_hash: str = None,
        timestamp: int = None,
        bits: str = None,
        nonce: int = None,
        txns: list = [],
    ) -> None:
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.txns: list = []

    @property
    def id(self) -> str:
        txns_ids = "".join(map(lambda t: t.id, self.txns))

        string_to_hash = (
            str(self.version)
            + str(self.prev_block_hash)
            + str(self.timestamp)
            + str(self.bits)
            + str(self.nonce)
            + str(txns_ids)
        )

        block_id = sha256d(string_to_hash)
        return block_id

    @property
    def is_valid_proof(self) -> bool:
        return int(self.id, 16) <= int(bits_to_target(self.bits), 16)

    def header(self) -> Any:
        """
        Block header
        """
        header = {
            "version": self.version,
            "prev_block_hash": self.prev_block_hash,
            "id": self.id,
            "bits": self.bits,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

        return header

    def json(self) -> dict:
        block = {}
        block["_id"] = self.id
        block["version"] = self.version
        block["prev_block_hash"] = self.prev_block_hash
        block["timestamp"] = self.timestamp
        block["bits"] = self.bits
        block["nonce"] = self.nonce
        block["txns"] = []

        for tx in self.txns:
            block["txns"].append(tx.json())

        return block

    def serialize(self, to_json=True) -> bytes:
        return msgpack.packb(self.json(), use_bin_type=True)

    def deserialize(self, block_serialized: str) -> None:
        pass

    def validate(self) -> bool:
        """
        Validate:
        1) [X] POW
        2) [ ] Coins supply
        3) [ ] Transactions
        4) [ ] Block Size
        5) [ ] Reward + Fees
        6) [ ] Timestamp
        """
        if not self.is_valid_proof:
            return False

        return True

    def save(self) -> None:
        client = MongoClient(port=27017)
        db=client.luracoin
        
        print("=======")
        print(self.json())
        print("=======")

        main()

    def create(self, propagate: bool = True) -> None:
        pass
