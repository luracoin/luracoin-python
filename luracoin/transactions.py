import msgpack
import ecdsa
import json
from typing import NamedTuple, Union
import binascii
from binascii import unhexlify

from luracoin.wallet import pubkey_to_address
from luracoin.config import Config
from luracoin.helpers import (
    mining_reward,
    sha256d,
    bytes_to_signing_key,
    little_endian_to_int
)

class Transaction:
    def __init__(
        self,
        chain: int = 0,
        nonce: int = 0,
        fee: int = 0,
        value: int = 0,
        to_address: str = None,
        unlock_sig: str = None,
    ) -> None:
        self.chain = chain
        self.nonce = nonce
        self.fee = fee
        self.value = value
        self.to_address = to_address
        self.unlock_sig = unlock_sig

    @property
    def is_coinbase(self) -> bool:
        return (
            len(self.txins) == 1
            and str(self.txins[0].to_spend.txid) == Config.COINBASE_TX_ID
        )

    def json(self) -> dict:
        return {
            "chain": self.chain,
            "nonce": self.nonce,
            "fee": self.fee,
            "value": self.value,
            "to_address": self.to_address,
            "unlock_sig": self.unlock_sig,
        }

    def serialize(self, to_sign=False) -> bytes:
        chain = self.chain.to_bytes(1, byteorder="little", signed=False)
        nonce = self.nonce.to_bytes(4, byteorder="little", signed=False)
        fee = self.fee.to_bytes(4, byteorder="little", signed=False)
        value = self.value.to_bytes(8, byteorder="little", signed=False)
        to_address = str.encode(self.to_address)
        
        if self.unlock_sig:
            unlock_sig = str.encode(self.unlock_sig)

        serialized = chain + nonce + fee + value + to_address

        if not to_sign and self.unlock_sig:
            serialized += unlock_sig

        return serialized

    def deserialize(self, serialized_hex: str):
        self.chain = little_endian_to_int(serialized_hex[0:2])
        self.nonce = little_endian_to_int(serialized_hex[2:10])
        self.fee = little_endian_to_int(serialized_hex[10:18])
        self.value = little_endian_to_int(serialized_hex[18:34])
        self.to_address = binascii.unhexlify(serialized_hex[34:102]).decode()
        if len(serialized_hex) > 102:
            self.unlock_sig = binascii.unhexlify(serialized_hex[102:]).decode()

    @property
    def id(self) -> str:
        """
        The ID will be the hash SHA256 of all the txins and txouts.
        """
        msg = b""
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

    def validate(self) -> bool:
        """
        Validate a transaction. For a transaction to be valid it has to follow
        hese conditions:

        - Value is less than the total supply.
        - Tx size is less than the block size limit.
        - Value has to be equal or less than the spending transaction
        - Valid unlocking code
        """
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
        pass


def build_message(outpoint, pub_key: str) -> str:
    """
    TODO: https://bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
    """
    return sha256d(str(outpoint.txid) + str(outpoint.txout_idx) + pub_key)


def build_script_sig(signature: str, public_key: str) -> str:
    """
    <VARINT>SIGNATURE<VARINT>PUBLIC_KEY
    """
    return signature + public_key


def verify_signature(message: str, public_key: str, signature: str) -> bool:
    vk = ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
    return vk.verify(signature, message)


def deserialize_unlocking_script(unlocking_script: str) -> dict:
    pub_key = unlocking_script[:128]
    signature = unlocking_script[128:]

    return {
        "signature": signature,
        "public_key": pub_key,
        "address": pubkey_to_address(pub_key.encode())
    }


def is_valid_unlocking_script(
    unlocking_script: str, transaction_serialized: str
) -> bool:
    # TODO: This functions allows to spend all outpoints since we are
    # verifying the signature not the signature + matching public key.

    try:
        unlocking_script = deserialize_unlocking_script(unlocking_script)
        print(unlocking_script)
    except binascii.Error:
        return False

    message = transaction_serialized.encode()

    try:
        is_valid = verify_signature(
            message=message,
            public_key=bytes.fromhex(unlocking_script["public_key"]),
            signature=bytes.fromhex(unlocking_script["signature"]),
        )
    except ecdsa.keys.BadSignatureError:
        is_valid = False

    return is_valid


def sign_transaction(private_key: bytes, transaction_serialized: str) -> bytes:
    private_key = bytes_to_signing_key(private_key=private_key)
    vk = private_key.get_verifying_key()
    public_key = vk.to_string().hex()

    signature = private_key.sign(transaction_serialized.encode())

    return public_key + signature.hex()
