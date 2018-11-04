import logging
import os
from typing import Iterable, NamedTuple, Union

from .config import Config
from .helpers import sha256d, var_int

logging.basicConfig(
    level=getattr(logging, os.environ.get("TC_LOG_LEVEL", "INFO")),
    format="[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# Used to represent the specific output within a transaction.
OutPoint = NamedTuple("OutPoint", [("txid", str), ("txout_idx", int)])


class TxIn(NamedTuple):
    """Inputs to a Transaction."""

    # A reference to the output we're spending. This is None for coinbase
    # transactions.
    to_spend: Union[OutPoint, None]

    # The (signature, pubkey) pair which unlocks the TxOut for spending.
    unlock_sig: str
    # unlock_pk: bytes

    # A sender-defined sequence number which allows us replacement of the txn
    # if desired.
    sequence: int


class TxOut(NamedTuple):
    """Outputs from a Transaction."""

    # The number of Belushis this awards.
    value: int

    # The public key of the owner of this Txn.
    to_address: str


class UnspentTxOut(NamedTuple):
    value: int
    to_address: str

    # The ID of the transaction this output belongs to.
    txid: str
    txout_idx: int

    # Did this TxOut from from a coinbase transaction?
    is_coinbase: bool

    # The blockchain height this TxOut was included in the chain.
    height: int

    @property
    def outpoint(self):
        return OutPoint(self.txid, self.txout_idx)


class Transaction(NamedTuple):
    # Which version of transaction data structure we're using.
    version: int

    txins: Iterable[TxIn]
    txouts: Iterable[TxOut]

    # The block number or timestamp at which this transaction is unlocked.
    # < 500000000: Block number at which this transaction is unlocked.
    # >= 500000000: UNIX timestamp at which this transaction is unlocked.
    locktime: int = 0

    @property
    def is_coinbase(self) -> bool:
        return len(self.txins) == 1 and str(self.txins[0].to_spend.txid) == "0"

    @property
    def id(self) -> str:
        msg = ""
        for x in self.txins:
            msg = (
                msg
                + str(x.to_spend.txid)
                + str(x.to_spend.txout_idx)
                + str(x.unlock_sig)
                + str(x.sequence)
            )
        for y in self.txouts:
            msg = msg + str(y.value) + str(y.to_address)

        tx_id = sha256d(msg)
        return tx_id

    def make_msg(self):
        """
        TODO: Improve the message.
        bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
        """
        return self.id

    def serialize_transaction(self):
        total = ""
        version = self.version.to_bytes(
            2, byteorder="little", signed=False
        ).hex()

        # INPUTS:
        num_inputs = len(self.txins)
        if num_inputs <= 252:
            num_inputs = num_inputs.to_bytes(
                1, byteorder="little", signed=False
            ).hex()
        elif num_inputs <= 65535:
            num_inputs = (
                "fd"
                + num_inputs.to_bytes(
                    2, byteorder="little", signed=False
                ).hex()
            )
        elif num_inputs <= 4_294_967_295:
            num_inputs = (
                "fe"
                + num_inputs.to_bytes(
                    4, byteorder="little", signed=False
                ).hex()
            )
        else:
            num_inputs = (
                "ff"
                + num_inputs.to_bytes(
                    8, byteorder="little", signed=False
                ).hex()
            )

        total = version + num_inputs

        for i in self.txins:
            tx_id = i.to_spend.txid

            if i.to_spend.txid == 0:
                tx_id = Config.COINBASE_TX_ID

            # Output to spent
            if i.to_spend.txout_idx == -1:
                vout = "ffffffff"  # Index. ffffffff for Coinbase
            else:
                vout = i.to_spend.txout_idx.to_bytes(
                    4, byteorder="little", signed=False
                ).hex()

            script_sig = i.unlock_sig
            script_sig_size = var_int(len(script_sig))  # VarInt
            sequence = i.sequence.to_bytes(
                4, byteorder="little", signed=False
            ).hex()
            total = (
                total
                + str(tx_id)
                + vout
                + str(script_sig_size)
                + script_sig
                + sequence
            )

        # OUTPUTS:
        num_outputs = len(self.txouts)
        total = total + var_int(num_outputs)

        for o in self.txouts:
            value = o.value.to_bytes(8, byteorder="little", signed=False).hex()
            script_pub_key = o.to_address
            script_pub_key_size = var_int(len(script_pub_key))
            total = total + value + script_pub_key_size + script_pub_key

        return total


class Block(NamedTuple):
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
