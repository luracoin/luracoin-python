import plyvel
import ecdsa
from typing import NamedTuple, Union
import binascii
from binascii import unhexlify

from luracoin.wallet import pubkey_to_address
from luracoin.config import Config
from luracoin.helpers import (
    little_endian,
    mining_reward,
    sha256d,
    var_int,
    little_endian_to_int,
    bytes_to_signing_key,
)

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
        if isinstance(script_sig, bytes):
            script_sig = script_sig.hex()
        script_sig_size = var_int(len(script_sig))

        sequence = little_endian(num_bytes=4, data=self.sequence)

        total = (
            str(tx_id) + vout + str(script_sig_size) + script_sig + sequence
        )

        return total


class TxOut:
    def __init__(self, value: int = None, to_address: str = None) -> None:
        self.value = value
        self.to_address = to_address

    def serialize(self) -> str:
        value = little_endian(num_bytes=8, data=self.value)
        script_pub_key = self.to_address
        script_pub_key_size = var_int(len(script_pub_key))
        return value + script_pub_key_size + script_pub_key


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

        if not self.is_coinbase:
            for txin in self.txins:
                if not is_valid_unlocking_script(
                    unlocking_script=txin.unlock_sig, outpoint=txin.to_spend
                ):
                    return False

        return True

    def save(self, block_height: int) -> None:
        """
        Add a transaction to the chainstate. Inside the chainstate database,
        the following key/value pairs are stored:

        'c' + 32-byte transaction hash -> unspent transaction output record for
        that transaction. These records are only present for transactions that
        have at least one unspent output left.

        Each record stores:
            The version of the transaction.
            Whether the transaction was a coinbase or not.
            Which height block contains the transaction.
            Which outputs of that transaction are unspent.
            The scriptPubKey and amount for those unspent outputs.

            [TX VERSION][COINBASE][HEIGHT][NUM OUTPUTS][∞][OUTPUT_LEN][OUTPUT]
                  ^         ^        ^          ^              ^
              4 bytes   1 byte   4 bytes      VARINT         VARINT

        'B' -> 32-byte block hash: the block hash up to which the database
        represents the unspent transaction outputs
        """
        for index, output in enumerate(self.txouts):
            outputs = transaction_chainstate_serialise(
                transaction=self, output=output, block_height=block_height
            )

            db = plyvel.DB(
                Config.DATA_DIR + "chainstate", create_if_missing=True
            )
            db.put(
                b"c" + self.id.encode() + str(index).encode(), outputs.encode()
            )
            db.close()


def transaction_chainstate_deserialise(
    serialised_transaction_data: str
) -> dict:
    """
    Deserialise the transactio from the chainstate and returns a dictionary.
    The fields are the following:
        # Version: 1 bytes
        # Coinbase: 1 bytes
        # Height: 4 bytes
        # Value: 8 bytes
        # Address: The content left
    """
    tx: dict = {}
    cursor = 0
    total_length_data = len(serialised_transaction_data)

    # HEADER
    tx["version"] = little_endian_to_int(
        serialised_transaction_data[cursor : cursor + 2]
    )
    cursor += 2

    tx["is_coinbase"] = little_endian_to_int(
        serialised_transaction_data[cursor : cursor + 2]
    )
    cursor += 2

    tx["height"] = little_endian_to_int(
        serialised_transaction_data[cursor : cursor + 8]
    )
    cursor += 8

    tx["value"] = little_endian_to_int(
        serialised_transaction_data[cursor : cursor + 16]
    )
    cursor += 16

    tx["to_address"] = serialised_transaction_data[cursor:total_length_data]

    return tx


def transaction_chainstate_serialise(  # type: ignore
    transaction, output, block_height
) -> None:
    version = little_endian(num_bytes=1, data=transaction.version)

    if transaction.is_coinbase:
        coinbase = little_endian(num_bytes=1, data=1)
    else:
        coinbase = little_endian(num_bytes=1, data=0)

    height = little_endian(num_bytes=4, data=int(block_height))
    output_content = (
        little_endian(num_bytes=8, data=int(output.value)) + output.to_address
    )

    return version + coinbase + height + output_content


def build_message(outpoint: OutPoint, pub_key: str) -> str:
    """
    TODO: https://bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
    """
    return sha256d(str(outpoint.txid) + str(outpoint.txout_idx) + pub_key)


def build_script_sig(signature: str, public_key: str) -> str:
    """
    <VARINT>SIGNATURE<VARINT>PUBLIC_KEY
    """
    signature_size = little_endian(num_bytes=1, data=len(signature))
    pub_key_size = little_endian(num_bytes=1, data=len(public_key))
    return str(signature_size) + signature + str(pub_key_size) + public_key


def verify_signature(message: str, public_key: str, signature: str) -> bool:
    vk = ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
    return vk.verify(signature, message)


def deserialize_unlocking_script(unlocking_script: str) -> dict:
    counter = 0

    signature_size = little_endian_to_int(unlocking_script[0:2])
    counter += 2

    signature = unlocking_script[counter : counter + signature_size]
    counter += signature_size

    pub_key_size = little_endian_to_int(
        unlocking_script[counter : counter + 2]
    )
    counter += 2

    pub_key = unlocking_script[counter : counter + pub_key_size]

    return {"signature": signature, "public_key": pub_key}


def is_valid_unlocking_script(
    unlocking_script: str, outpoint: OutPoint
) -> bool:
    # TODO: This functions allows to spend all outpoints since we are
    # verifying the signature not the signature + matching public key.

    try:
        unlocking_script = deserialize_unlocking_script(unlocking_script)
    except binascii.Error:
        return False

    message = build_message(outpoint, unlocking_script["public_key"]).encode()

    try:
        is_valid = verify_signature(
            message=message,
            public_key=bytes.fromhex(unlocking_script["public_key"]),
            signature=bytes.fromhex(unlocking_script["signature"]),
        )
    except ecdsa.keys.BadSignatureError:
        is_valid = False

    return is_valid


def sign_transaction(private_key: bytes, outpoint: OutPoint) -> bytes:
    private_key = bytes_to_signing_key(private_key=private_key)
    vk = private_key.get_verifying_key()
    public_key = vk.to_string().hex()

    message = build_message(outpoint, public_key).encode()
    signature = private_key.sign(message)

    return signature
