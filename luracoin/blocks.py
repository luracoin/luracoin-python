import msgpack
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

    def json(self) -> dict:
        block = {}
        block["version"] = self.version
        block["prev_block_hash"] = self.prev_block_hash
        block["timestamp"] = self.timestamp
        block["bits"] = self.bits
        block["nonce"] = self.nonce
        block["txns"] = []

        for tx in self.txns:
            block["txns"].append(tx.json())

        return block

    def serialize(self) -> bytes:
        return msgpack.packb(self.json(), use_bin_type=True)

    def deserialize(self, block_serialized: str) -> None:
        deserialized_block = msgpack.unpackb(
            block_serialized, use_list=False, raw=False
        )

        self.version = deserialized_block["version"]
        self.prev_block_hash = deserialized_block["prev_block_hash"]
        self.timestamp = deserialized_block["timestamp"]
        self.bits = deserialized_block["bits"]
        self.nonce = deserialized_block["nonce"]

        for tx in deserialized_block["txns"]:
            transaction = Transaction(
                version=tx["version"], locktime=tx["locktime"]
            )

            txins = []
            for txin in tx["txins"]:
                deserialized_txin = TxIn()
                deserialized_txin.to_spend = OutPoint(
                    txid=txin["to_spend"][0], txout_idx=txin["to_spend"][1]
                )
                deserialized_txin.unlock_sig = txin["unlock_sig"]
                deserialized_txin.sequence = txin["sequence"]

                txins.append(deserialized_txin)

            txouts = []
            for txout in tx["txouts"]:
                deserialized_txout = TxOut()
                deserialized_txout.value = txout["value"]
                deserialized_txout.to_address = txout["to_address"]

                txouts.append(deserialized_txout)

            transaction.txins = txins
            transaction.txouts = txouts

            self.txns.append(transaction)

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

        db.close()

        process_block_transactions(self)

    def create(self, propagate: bool = True) -> None:
        pass


def process_block_transactions(block):
    """
    Add outputs to the chainstate and delete the inputs used.
    """
    for transaction in block.txns:
        for tx_spent in transaction.txins:
            if tx_spent.to_spend.txid != Config.COINBASE_TX_ID:
                print(
                    f"Remove from chainstate: {tx_spent.to_spend.txid} -> {tx_spent.to_spend.txout_idx}"
                )

        # add_tx_to_chainstate(tx, int(block.txns[0].txins[0].unlock_sig))
        print(
            f"Add to chainstate {transaction} {int(block.txns[0].txins[0].unlock_sig)}"
        )


'''
def process_block_transactions(block):
    """
    Add outputs to the chainstate and delete the inputs used.
    """
    for tx in block.txns:
        for tx_spent in tx.txins:
            if tx_spent.to_spend.txid != 0:
                remove_tx_from_chainstate(
                    tx_spent.to_spend.txid, tx_spent.to_spend.txout_idx
                )

        add_tx_to_chainstate(tx, int(block.txns[0].txins[0].unlock_sig))


def remove_tx_from_chainstate(tx: str, vout: int) -> None:
    """
    Remove UTXO from the chainstate.

    :param tx: Transaction ID
    :param vout: Which output
    """
    db = plyvel.DB(Config.DATA_DIR + "chainstate", create_if_missing=True)
    db.delete(b"c" + tx.encode() + str(vout).encode())
    db.close()


def read_tx_from_chainstate(tx: str) -> dict:
    """
    Read a transaction from the LevelDB Chainstate. And returns a Dictionary
    with all the information.
    """
    tx_info = {
        "version": int.from_bytes(
            binascii.unhexlify(tx[0:2]), byteorder="little"
        ),
        "coinbase": int.from_bytes(
            binascii.unhexlify(tx[2:4]), byteorder="little"
        ),
        "height": int.from_bytes(
            binascii.unhexlify(tx[4:12]), byteorder="little"
        ),
        "output": tx[12:],
    }

    # print(json.dumps(tx_info, indent=4))
    return tx_info
'''
