from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import (little_endian, little_endian_to_int, sha256d,
                              var_int, var_int_to_bytes)


class Block:
    # A version integer.
    version: int

    # A hash of the previous block's header.
    prev_block_hash: str

    # A UNIX timestamp of when this block was created.
    timestamp: int

    # The difficulty target; i.e. the hash of this block header must be under
    # (2 ** 256 >> bits) to consider work proved.
    bits: int

    # The value that's incremented in an attempt to get the block header to
    # hash to a value below `bits`.
    nonce: int

    # Transaction list
    txns: list

    def __init__(
        self,
        version: int = None,
        prev_block_hash: str = None,
        timestamp: int = None,
        bits: int = None,
        nonce: int = None,
        txns: list = [],
    ) -> None:
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.txns = txns

    @property
    def id(self) -> str:
        txns_ids = ""
        for t in self.txns:
            txns_ids = txns_ids + t.id

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

    def serialize(self) -> str:
        """
        Magic bytes (4 bytes)
        Block header (82 bytes)
        -> Block version (4 bytes)
        -> Prev hash (32 bytes)
        -> Block hash (32 bytes)
        -> Difficulty bits (4 bytes)
        -> Timestamp (4 bytes)
        -> Nonce (6 bytes)
        """
        version = little_endian(num_bytes=4, data=self.version)
        bits = little_endian(num_bytes=4, data=self.bits)
        timestamp = little_endian(num_bytes=4, data=self.timestamp)
        nonce = little_endian(num_bytes=6, data=self.nonce)

        total = (
            Config.MAGIC_BYTES
            + version
            + self.prev_block_hash
            + self.id
            + bits
            + timestamp
            + nonce
        )

        # Tx_count
        tx_count = var_int(len(self.txns))
        total += tx_count

        # Tx_data
        for tx in self.txns:
            total += tx.serialize()

        return total

    def split_serialized_transactions(self, serialized_txns: str) -> list:
        num_bytes = var_int_to_bytes(serialized_txns[0:2])
        if num_bytes == 1:
            num_txs_serialized = serialized_txns[0:2]
        else:
            num_txs_serialized = serialized_txns[2:num_bytes*2]

        num_txs = little_endian_to_int(num_txs_serialized)
        
        tx_list = []
        bytes_counter = num_bytes * 2  # Ignore the num txs.
        for _ in range(num_txs):
            # Version (2 bytes)
            # Inputs (VAR INT)
            #    TX ID
            #    TVOUT
            # Outputs (VAR INT)
            #    Value (8 bytes)
            #    Script Size

        return tx_list


    def deserialize(self, block_serialized: str) -> None:
        magic = block_serialized[0:8]
        version = block_serialized[8:16]
        prev_hash = block_serialized[16:80]
        # block_hash = block_serialized[80:144]
        bits = block_serialized[144:152]
        timestamp = block_serialized[152:160]
        nonce = block_serialized[160:172]

        if magic != Config.MAGIC_BYTES:
            raise BlockNotValidError

        self.version = little_endian_to_int(version)
        self.prev_block_hash = prev_hash
        self.timestamp = little_endian_to_int(timestamp)
        self.bits = little_endian_to_int(bits)
        self.nonce = little_endian_to_int(nonce)

        tx_list = self.split_serialized_transactions(block_serialized[174:])

        """
        txns = deserialize_transaction(block_serialized[172:])
        for t in txns:
            self.txns.append(t)
        """

    def validate(self) -> None:
        pass
