import plyvel
from typing import Any
from luracoin.config import Config
from luracoin.exceptions import BlockNotValidError
from luracoin.helpers import (
    little_endian,
    little_endian_to_int,
    sha256d,
    var_int,
    var_int_to_bytes,
    bits_to_target,
    block_index_disk_write,
)
from luracoin.transactions import OutPoint, Transaction, TxIn, TxOut
from luracoin.chain import (
    serialise_block_to_save,
    get_current_file_number,
    get_current_blk_file,
)


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

    def header(self, serialised: bool = False) -> Any:
        """
        Block header, serialised or as a dict
        """
        if serialised:
            version = little_endian(num_bytes=4, data=self.version)
            timestamp = little_endian(num_bytes=4, data=self.timestamp)
            nonce = little_endian(num_bytes=6, data=self.nonce)

            return (
                version
                + self.prev_block_hash
                + self.id
                + self.bits
                + timestamp
                + nonce
            )

        header = {
            "version": self.version,
            "prev_block_hash": self.prev_block_hash,
            "id": self.id,
            "bits": self.bits,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

        return header

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
        total = Config.MAGIC_BYTES + self.header(serialised=True)

        # Tx_count
        tx_count = var_int(len(self.txns))
        total += tx_count

        # Tx_data
        for tx in self.txns:
            total += tx.serialize()

        return total

    def deserialize(self, block_serialized: str) -> None:
        magic = block_serialized[0:8]
        block_version = block_serialized[8:16]
        prev_hash = block_serialized[16:80]
        # block_hash = block_serialized[80:144]
        bits = block_serialized[144:152]
        timestamp = block_serialized[152:160]
        nonce = block_serialized[160:172]

        if magic != Config.MAGIC_BYTES:
            raise BlockNotValidError

        self.version = little_endian_to_int(block_version)
        self.prev_block_hash = prev_hash
        self.timestamp = little_endian_to_int(timestamp)
        self.bits = bits
        self.nonce = little_endian_to_int(nonce)

        block_body = block_serialized[172:]

        num_bytes = var_int_to_bytes(block_body[0:2])
        if num_bytes == 1:
            num_txs_serialized = block_body[0:2]
            num_txs_total_chars_len = 2
        else:
            num_txs_serialized = block_body[2 : num_bytes * 2]
            num_txs_total_chars_len = 2 + num_bytes * 2

        num_txs = little_endian_to_int(num_txs_serialized)

        block_body = block_serialized[172 + num_txs_total_chars_len :]

        for _ in range(num_txs):
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
            version = little_endian_to_int(block_body[:4])
            block_body = block_body[4:]

            # Num Inputs
            bytes_for_num_inputs = var_int_to_bytes(block_body[0:2])
            if bytes_for_num_inputs == 1:
                num_inputs_serialized = block_body[0:2]
                num_inputs_total_chars_len = 2
            else:
                num_inputs_serialized = block_body[
                    2 : bytes_for_num_inputs * 2
                ]
                num_inputs_total_chars_len = 2 + bytes_for_num_inputs * 2

            num_inputs = little_endian_to_int(num_inputs_serialized)
            block_body = block_body[num_inputs_total_chars_len:]

            txin_list = []
            for _ in range(num_inputs):
                tx_id = block_body[0:64]
                vout = little_endian_to_int(block_body[64:72])
                block_body = block_body[72:]

                bytes_for_unlock_sig_size = var_int_to_bytes(block_body[0:2])
                if bytes_for_unlock_sig_size == 1:
                    unlock_sig_size_serialized = block_body[0:2]
                    unlock_sig_size_total_chars_len = 2
                else:
                    unlock_sig_size_serialized = block_body[
                        2 : bytes_for_unlock_sig_size * 2
                    ]
                    unlock_sig_size_total_chars_len = (
                        2 + bytes_for_unlock_sig_size * 2
                    )

                unlock_sig_size = little_endian_to_int(
                    unlock_sig_size_serialized
                )
                block_body = block_body[unlock_sig_size_total_chars_len:]

                unlock_sig = block_body[0:unlock_sig_size]
                block_body = block_body[unlock_sig_size:]

                sequence = little_endian_to_int(block_body[0:8])
                block_body = block_body[8:]

                txin_list.append(
                    TxIn(
                        to_spend=OutPoint(tx_id, vout),
                        unlock_sig=unlock_sig,
                        sequence=sequence,
                    )
                )

            # Num outputs
            bytes_for_num_outputs = var_int_to_bytes(block_body[0:2])
            if bytes_for_num_outputs == 1:
                num_outputs_serialized = block_body[0:2]
                num_outputs_total_chars_len = 2
            else:
                num_outputs_serialized = block_body[
                    2 : bytes_for_num_outputs * 2
                ]
                num_outputs_total_chars_len = 2 + bytes_for_num_outputs * 2

            num_outputs = little_endian_to_int(num_outputs_serialized)
            block_body = block_body[num_outputs_total_chars_len:]

            txout_list = []
            for _ in range(num_outputs):
                txout = TxOut()
                value = little_endian_to_int(block_body[0:16])

                txout.value = value
                block_body = block_body[16:]

                bytes_for_script_size = var_int_to_bytes(block_body[0:2])
                if bytes_for_script_size == 1:
                    script_size_serialized = block_body[0:2]
                    script_size_total_chars_len = 2
                else:
                    script_size_serialized = block_body[
                        2 : bytes_for_script_size * 2
                    ]
                    script_size_total_chars_len = 2 + bytes_for_script_size * 2

                script_size = little_endian_to_int(script_size_serialized)
                block_body = block_body[script_size_total_chars_len:]

                script = block_body[0:script_size]

                txout.to_address = script
                block_body = block_body[script_size:]

                txout_list.append(TxOut(value=value, to_address=script))

            self.txns.append(
                Transaction(
                    version=version, txins=txin_list, txouts=txout_list
                )
            )

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
        """
        Save the block in the file system. And update some values on LevelDB.
        TODO: Save 'b' key/value and process transactions.

        'l' -> Actual file number (eg. blk00045.dat)
        'b' -> Current block height
        'c' -> Validation process

        'b' + 32-byte block hash -> block index record. Each record stores:
            The block header.
            The height.
            The number of transactions.
            To what extent this block is validated.
            In which file, and where in that file, the block data is stored.

        'b' + 6-byte block height ->
            6-byte File name in which the block data is stored.
            32-byte block hash
        """
        if not self.validate():
            raise ValueError("Invalid block")

        serialized_block = serialise_block_to_save(self.serialize())
        current_file = get_current_blk_file()

        filename = Config.BLOCKS_DIR + current_file
        with open(filename, "ab+") as f:
            f.write(serialized_block.encode())

        current_file_number = get_current_file_number()

        db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)

        # Save the current file number
        db.put(b"l", current_file_number.encode())

        # Get and increment the current block height
        current_block_height = int(db.get(b"b", 0))
        current_block_height += 1
        db.put(b"b", str(current_block_height).encode())

        # Save block index record with the header and other serialised data
        db.put(
            b"b" + self.id.encode(),
            block_index_disk_write(
                {
                    "header": self.header(serialised=True),
                    "height": current_block_height,
                    "txns": len(self.txns),
                    "file": current_file_number,
                    "is_validated": True,
                }
            ).encode(),
        )

        db.put(
            b"b" + str(current_block_height).encode(),
            (
                little_endian(num_bytes=3, data=int(current_file_number))
                + self.id
            ).encode(),
        )

        # WIP: db.put(b"b")) -- 'b' + 32-byte block hash -> block index record.
        db.close()

        # process_block_transactions(deserialize_blk)

    def create(self, propagate: bool = True) -> None:
        pass
