from typing import NamedTuple, Union

from luracoin.config import Config
from luracoin.helpers import little_endian, mining_reward, sha256d, var_int

# Used to represent the specific output within a transaction.
OutPoint = NamedTuple(
    "OutPoint", [("txid", Union[str, int]), ("txout_idx", Union[str, int])]
)


class TxIn:
    def __init__(
        self,
        to_spend: Union[OutPoint, None] = None,
        unlock_sig: str = None,
        sequence: int = None,
    ) -> None:
        self.to_spend = to_spend
        self.unlock_sig = unlock_sig
        self.sequence = sequence

    def serialize(self) -> str:
        tx_id = self.to_spend.txid

        if self.to_spend.txid == 0:
            tx_id = Config.COINBASE_TX_ID

        if self.to_spend.txout_idx == Config.COINBASE_TX_INDEX:
            vout = Config.COINBASE_TX_INDEX
        else:
            vout = little_endian(  # type: ignore
                num_bytes=4, data=self.to_spend.txout_idx
            )

        script_sig = self.unlock_sig
        script_sig_size = var_int(len(script_sig))

        sequence = little_endian(num_bytes=4, data=self.sequence)

        total = (
            str(tx_id) + vout + str(script_sig_size) + script_sig + sequence
        )

        return total

    def deserialize(self) -> None:
        pass


class TxOut:
    def __init__(self, value: int = None, to_address: str = None) -> None:
        self.value = value
        self.to_address = to_address

    def serialize(self) -> str:
        value = little_endian(num_bytes=8, data=self.value)
        script_pub_key = self.to_address
        script_pub_key_size = var_int(len(script_pub_key))
        return value + script_pub_key_size + script_pub_key

    def deserialize(self) -> None:
        pass


class Transaction:
    def __init__(
        self,
        version: int = 0,
        txins: list = [],
        txouts: list = [],
        locktime: int = 0,
    ) -> None:
        self.version = version
        self.txins = txins
        self.txouts = txouts
        self.locktime = locktime

    @property
    def is_coinbase(self) -> bool:
        return (
            len(self.txins) == 1
            and str(self.txins[0].to_spend.txid) == Config.COINBASE_TX_ID
        )

    @property
    def id(self) -> str:
        """
        The ID will be the hash SHA256 of all the txins and txouts.
        """
        msg = ""
        for x in self.txins:
            msg = msg + x.serialize()
        for y in self.txouts:
            msg = msg + y.serialize()

        tx_id = sha256d(msg)
        return tx_id

    def make_msg(self) -> str:
        """
        TODO: Improve the message.
        bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
        """
        return self.id

    def serialize(self) -> str:
        # Version
        serialized_tx = little_endian(num_bytes=2, data=self.version)

        # INPUTS:
        serialized_tx += var_int(len(self.txins))

        for txin in self.txins:
            serialized_tx += txin.serialize()

        # OUTPUTS:
        serialized_tx += var_int(len(self.txouts))

        for txout in self.txouts:
            serialized_tx += txout.serialize()

        return serialized_tx

    def validate(self) -> bool:
        """
        Validate a transaction. For a transaction to be valid it has to follow
        hese conditions:

        - Value is less than the total supply.
        - Tx size is less than the block size limit.
        - Value has to be equal or less than the spending transaction
        - Valid unlocking code
        """
        if not self.txins or not self.txouts:
            return False

        total_value = 0
        for to in self.txouts:
            total_value = total_value + to.value

        if self.is_coinbase and total_value > (
            mining_reward() * Config.BELUSHIS_PER_COIN
        ):
            return False

        return True
