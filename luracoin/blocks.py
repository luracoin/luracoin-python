from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import (
    little_endian,
    little_endian_to_int,
    sha256d,
    var_int,
    var_int_to_bytes
)
from luracoin.transactions import Transaction


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

        block_body = block_serialized[172:]

        num_bytes = var_int_to_bytes(block_body[0:2])
        if num_bytes == 1:
            num_txs_serialized = block_body[0:2]
            num_txs_total_chars_len = 2
        else:
            num_txs_serialized = block_body[2:num_bytes*2]
            num_txs_total_chars_len = 2 + num_bytes * 2

        num_txs = little_endian_to_int(num_txs_serialized)

        print("Number transactions: ")
        print(num_txs)

        block_body = block_serialized[172 + num_txs_total_chars_len:]

        for _ in range(num_txs):
            print("===============================")
            transaction = Transaction()
            # - Version (2 bytes)
            # - Num Inputs (VARINT)
            #   - TX ID (32 bytes)
            #   - VOUT (4 bytes)
            #   - unlock_sig_size (VARINT)
            #   - unlock_sig (VARINT)
            #   - sequence (4 bytes)
            # - Num Outputs
            #   - Value (8 bytes)
            #   - Script Size (VARINT)
            #   - Script (VARINT)
            
            # Version
            transaction.version = little_endian_to_int(block_body[:4])
            print(f"Version: {transaction.version}")
            block_body = block_body[4:]

            # Num Inputs
            bytes_for_num_inputs = var_int_to_bytes(block_body[0:2])
            if bytes_for_num_inputs == 1:
                num_inputs_serialized = block_body[0:2]
                num_inputs_total_chars_len = 2
            else:
                num_inputs_serialized = block_body[2:bytes_for_num_inputs*2]
                num_inputs_total_chars_len = 2 + bytes_for_num_inputs * 2

            num_inputs = little_endian_to_int(num_inputs_serialized)
            print(f"Number of inputs: {num_inputs}")
            block_body = block_body[num_inputs_total_chars_len:]

            for _ in range(num_inputs):
                print("- TXIN: ")
                tx_id = block_body[0:64]
                print(f" -- Transaction ID: {tx_id}")
                vout = block_body[64:72]
                print(f" -- Vout: {vout}")
                block_body = block_body[72:]

                bytes_for_unlock_sig_size = var_int_to_bytes(block_body[0:2])
                if bytes_for_unlock_sig_size == 1:
                    unlock_sig_size_serialized = block_body[0:2]
                    unlock_sig_size_total_chars_len = 2
                else:
                    unlock_sig_size_serialized = block_body[2:bytes_for_unlock_sig_size*2]
                    unlock_sig_size_total_chars_len = 2 + bytes_for_unlock_sig_size * 2

                unlock_sig_size = little_endian_to_int(unlock_sig_size_serialized)
                print(f" -- Unlock Sig size: {unlock_sig_size}")
                block_body = block_body[unlock_sig_size_total_chars_len:]

                unlock_sig = block_body[0:unlock_sig_size]
                print(f" -- Unlock Sig: {unlock_sig}")
                block_body = block_body[unlock_sig_size:]

                sequence = block_body[0:8]
                print(f" -- Sequence: {sequence}")
                block_body = block_body[8:]

            # Num outputs
            bytes_for_num_outputs = var_int_to_bytes(block_body[0:2])
            if bytes_for_num_outputs == 1:
                num_outputs_serialized = block_body[0:2]
                num_outputs_total_chars_len = 2
            else:
                num_outputs_serialized = block_body[2:bytes_for_num_outputs*2]
                num_outputs_total_chars_len = 2 + bytes_for_num_outputs * 2

            num_outputs = little_endian_to_int(num_outputs_serialized)
            print(f"Number of outputs: {num_outputs}")
            block_body = block_body[num_outputs_total_chars_len:]

            for _ in range(num_outputs):
                print("- TXOUT: ")
                value = little_endian_to_int(block_body[0:16])
                print(f"-- Value: {value}")
                block_body = block_body[16:]

                bytes_for_script_size = var_int_to_bytes(block_body[0:2])
                if bytes_for_script_size == 1:
                    script_size_serialized = block_body[0:2]
                    script_size_total_chars_len = 2
                else:
                    script_size_serialized = block_body[2:bytes_for_script_size*2]
                    script_size_total_chars_len = 2 + bytes_for_script_size * 2

                script_size = little_endian_to_int(script_size_serialized)
                print(f"-- Script Size: {script_size}")
                block_body = block_body[script_size_total_chars_len:]

                script = block_body[0:script_size]
                print(f" -- Script: {script}")
                block_body = block_body[script_size:]


            print("===============================")

            # Num inputs here
            


    def validate(self) -> None:
        pass
