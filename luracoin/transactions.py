import binascii
import hashlib
from typing import Optional, Union

import redis
from coincurve import PublicKey, ecdsa as secp256k1_ecdsa

from luracoin import errors
from luracoin.exceptions import TransactionNotValid
from luracoin.wallet import is_valid_address, pubkey_to_address
from luracoin.config import Config
from luracoin.helpers import sha256d, bytes_to_signing_key

SECP256K1_ORDER = int(
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
    16,
)

_MEMPOOL_INSERT_SCRIPT = """
local claimed = redis.call('GET', KEYS[1])
if claimed and claimed ~= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SET', KEYS[2], ARGV[2])
return 1
"""


class Transaction:
    def __init__(
        self,
        chain: int = 0,
        nonce: int = 0,
        fee: int = 0,
        value: int = 0,
        from_address: str = None,
        to_address: str = None,
        unlock_sig: bytes = None,
    ) -> None:
        self.chain = chain
        self.nonce = nonce
        self.fee = fee
        self.value = value
        self.from_address = from_address
        self.to_address = to_address
        self.unlock_sig = unlock_sig

    @property
    def is_coinbase(self) -> bool:
        return self.unlock_sig == Config.COINBASE_UNLOCK_SIGNATURE

    def sign(self, private_key) -> "Transaction":
        signature = sign_transaction(
            private_key=private_key,
            transaction_serialized=self.serialize(to_sign=True),
        )
        self.unlock_sig = signature
        return self

    def json(self) -> dict:
        result = {
            "id": self.id,
            "chain": self.chain,
            "nonce": self.nonce,
            "fee": self.fee,
            "value": self.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "unlock_sig": None,
        }
        if self.unlock_sig:
            result["unlock_sig"] = self.unlock_sig.hex()
        return result

    def serialize(self, to_sign=False) -> bytes:
        chain = self.chain.to_bytes(1, byteorder="little", signed=False)
        nonce = self.nonce.to_bytes(4, byteorder="little", signed=False)
        fee = self.fee.to_bytes(4, byteorder="little", signed=False)
        value = self.value.to_bytes(8, byteorder="little", signed=False)
        from_address = str.encode(self.from_address)
        to_address = str.encode(self.to_address)

        if self.unlock_sig:
            unlock_sig = self.unlock_sig

        serialized = chain + nonce + fee + value + from_address + to_address

        if not to_sign and self.unlock_sig:
            serialized += unlock_sig

        return serialized

    def deserialize(self, serialized_bytes: bytes):
        if not isinstance(serialized_bytes, bytes) or len(
            serialized_bytes
        ) not in (
            85,
            Config.TRANSACTION_LENGTH,
        ):
            raise TransactionNotValid(
                "Non-canonical serialized transaction length."
            )
        self.chain = int.from_bytes(serialized_bytes[0:1], byteorder="little")
        self.nonce = int.from_bytes(serialized_bytes[1:5], byteorder="little")
        self.fee = int.from_bytes(serialized_bytes[5:9], byteorder="little")
        self.value = int.from_bytes(serialized_bytes[9:17], byteorder="little")
        self.from_address = serialized_bytes[17:51].decode("utf-8")
        self.to_address = serialized_bytes[51:85].decode("utf-8")
        self.unlock_sig = None
        if len(serialized_bytes) == Config.TRANSACTION_LENGTH:
            self.unlock_sig = serialized_bytes[85:]
        return self

    @property
    def id(self) -> str:
        """Double-SHA256 of the canonical signed transaction bytes."""
        return sha256d(self.serialize())

    def make_msg(self) -> str:
        """
        TODO: Improve the message.
        bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
        """
        return self.id

    def validate_fields(self, raise_exception=False) -> bool:
        """
        Checks that the transaction has the correct fields.
        """
        if (
            not isinstance(self.chain, int)
            or self.chain < 0
            or self.chain > 255
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_CHAIN)
            return False

        if (
            not isinstance(self.nonce, int)
            or self.nonce < 0
            or self.nonce > 4_294_967_295
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_NONCE)
            return False

        if (
            not isinstance(self.fee, int)
            or self.fee < 0
            or self.fee > 4_294_967_295
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_FEE)
            return False

        if (
            not isinstance(self.value, int)
            or self.value <= 0
            or self.value > 18_446_744_073_709_551_615
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_VALUE)
            return False

        if (
            not self.from_address
            or len(self.from_address) != 34
            or (self.from_address == "0" * 34 and not self.is_coinbase)
            or (
                self.from_address != "0" * 34
                and not is_valid_address(self.from_address)
            )
        ):
            if raise_exception:
                raise TransactionNotValid(
                    errors.TRANSACTION_FIELD_FROM_ADDRESS
                )
            return False

        if (
            not isinstance(self.unlock_sig, bytes)
            or len(self.unlock_sig) != 128
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_SIGNATURE)
            return False

        # The all-zero value is a protocol sentinel, not a spendable address.
        # No staking or burn rule exists in this alpha, so accepting funds to
        # it would create an undocumented, irreversible economic operation.
        if self.to_address == Config.STAKING_ADDRESS:
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_INVALID_STAKING)
            return False

        if not is_valid_address(self.to_address):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_TO_ADDRESS)
            return False

        return True

    def validate(
        self,
        raise_exception: bool = False,
        account: Optional[dict] = None,
    ) -> bool:
        """
        Validate a transaction. For a transaction to be valid it has to follow
        these conditions:
        """
        if not self.validate_fields(raise_exception=raise_exception):
            return False

        if self.chain != Config.CHAIN_ID:
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_FIELD_CHAIN)
            return False

        if (
            self.unlock_sig != Config.COINBASE_UNLOCK_SIGNATURE
            and not is_valid_unlocking_script(
                unlocking_script=self.unlock_sig,
                transaction_serialized=self.serialize(to_sign=True),
                from_address=self.from_address,
            )
        ):
            if raise_exception:
                raise TransactionNotValid(errors.TRANSACTION_INVALID_SIGNATURE)
            return False

        # Balance and nonce checks (skip for coinbase)
        if not self.is_coinbase:
            from luracoin.chain import Chain

            if account is None:
                chain = Chain()
                account = chain.get_account(self.from_address)

            if not account:
                if raise_exception:
                    raise TransactionNotValid(errors.TRANSACTION_NO_BALANCE)
                return False

            try:
                balance = int(account["balance"])
                current_nonce = int(account["nonce"])
            except (KeyError, TypeError, ValueError):
                if raise_exception:
                    raise TransactionNotValid(errors.TRANSACTION_NO_BALANCE)
                return False
            if (
                not 0 <= balance <= 0xFFFFFFFFFFFFFFFF
                or not 0 <= current_nonce <= 0xFFFFFFFF
            ):
                if raise_exception:
                    raise TransactionNotValid(errors.TRANSACTION_NO_BALANCE)
                return False

            if balance < self.value + self.fee:
                if raise_exception:
                    raise TransactionNotValid(errors.TRANSACTION_NO_BALANCE)
                return False

            if self.nonce != current_nonce + 1:
                if raise_exception:
                    raise TransactionNotValid(errors.TRANSACTION_INVALID_NONCE)
                return False

        return True

    def to_transaction_pool(self) -> bool:
        if self.is_coinbase:
            return False

        redis_client = redis.Redis(
            host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB
        )
        from luracoin.chain import Chain

        account = Chain().get_account(self.from_address)
        if not account:
            return False
        try:
            account = {
                "balance": int(account["balance"]),
                "nonce": int(account["nonce"]),
            }
        except (KeyError, TypeError, ValueError):
            return False
        pending_count = self.nonce - account["nonce"] - 1
        if pending_count < 0 or pending_count >= Config.MAX_TX_PER_BLOCK:
            return False

        # Permit a contiguous sequence of pending outbound transactions while
        # validating each debit against a simulated sender account.
        for nonce in range(account["nonce"] + 1, self.nonce):
            nonce_key = self.mempool_nonce_key_for(
                self.chain, self.from_address, nonce
            )
            pending_id = redis_client.get(nonce_key)
            if not pending_id:
                return False
            pending_bytes = redis_client.get(pending_id)
            if not pending_bytes:
                return False
            try:
                pending = Transaction().deserialize(pending_bytes)
            except (TransactionNotValid, UnicodeDecodeError):
                return False
            if (
                pending.from_address != self.from_address
                or pending.nonce != nonce
                or not pending.validate(account=account)
            ):
                return False
            account["balance"] -= pending.value + pending.fee
            account["nonce"] = pending.nonce
            if pending.to_address == self.from_address:
                account["balance"] += pending.value

        if not self.validate(account=account):
            return False

        inserted = redis_client.eval(
            _MEMPOOL_INSERT_SCRIPT,
            2,
            self.mempool_nonce_key,
            self.id,
            self.id,
            self.serialize(),
        )
        return bool(inserted)

    @property
    def mempool_nonce_key(self) -> str:
        """Redis key reserving one sender/nonce pair in the mempool."""
        return self.mempool_nonce_key_for(
            self.chain, self.from_address, self.nonce
        )

    @staticmethod
    def mempool_nonce_key_for(chain: int, address: str, nonce: int) -> str:
        return f"nonce:{chain}:{address}:{nonce}"

    def save(self, block_height: int, tx_index: int = 0) -> None:
        """
        Save a transaction to the chainstate and update account balances.
        Luracoin uses an Account Model (not UTXO).

        Inside the chainstate database:
        - 't' + 32-byte tx hash -> block_height (4 bytes) + tx_index (2 bytes)
        - Account balances are updated via get_account() / set_account()

        For non-coinbase transactions:
        - Subtract (value + fee) from from_address balance
        - Add value to to_address balance
        - Increment from_address nonce
        """
        from luracoin.chain import Chain, get_value, set_value, set_values

        chain = Chain()

        if self.is_coinbase:
            raise TransactionNotValid(
                "Coinbase state transitions may only be applied "
                "by Block.save()."
            )

        # Store tx record indexed by hash. Retrying the same transaction at the
        # same location is a no-op; moving an existing tx is rejected.
        tx_record = block_height.to_bytes(
            4, byteorder="little", signed=False
        ) + tx_index.to_bytes(2, byteorder="little", signed=False)
        tx_key = b"t" + self.id.encode()
        existing_record = get_value(Config.DATABASE_CHAINSTATE, tx_key)
        if existing_record:
            if existing_record != tx_record:
                raise TransactionNotValid(
                    "Transaction already saved elsewhere."
                )
            return

        state_marker = b"\x00applied-tx:" + bytes.fromhex(self.id)
        applied_record = get_value(Config.DATABASE_ACCOUNTS, state_marker)
        if applied_record:
            if applied_record != tx_record:
                raise TransactionNotValid(
                    "Transaction state was applied at another location."
                )
            set_value(Config.DATABASE_CHAINSTATE, tx_key, tx_record)
            return

        if not self.validate():
            raise TransactionNotValid("Cannot save an invalid transaction.")

        # Debit sender (skip for coinbase)
        updates = {}
        if not self.is_coinbase:
            sender = chain.get_account(self.from_address) or {
                "balance": 0,
                "nonce": 0,
            }
            sender["balance"] -= self.value + self.fee
            sender["nonce"] = self.nonce
            updates[self.from_address.encode()] = sender

        # Credit receiver
        if self.to_address == self.from_address and not self.is_coinbase:
            receiver = sender
        else:
            receiver = chain.get_account(self.to_address) or {
                "balance": 0,
                "nonce": 0,
            }
        receiver["balance"] += self.value
        if receiver["balance"] > 0xFFFFFFFFFFFFFFFF:
            raise TransactionNotValid("Receiver balance would overflow.")
        updates[self.to_address.encode()] = receiver

        import json

        account_values = {
            key: json.dumps(value, sort_keys=True).encode()
            for key, value in updates.items()
        }
        account_values[state_marker] = tx_record
        set_values(Config.DATABASE_ACCOUNTS, account_values)
        set_value(Config.DATABASE_CHAINSTATE, tx_key, tx_record)


def build_message(outpoint, pub_key: str) -> str:
    """Build the legacy outpoint message."""
    return sha256d(str(outpoint.txid) + str(outpoint.txout_idx) + pub_key)


def build_script_sig(signature: str, public_key: str) -> str:
    """
    <VARINT>SIGNATURE<VARINT>PUBLIC_KEY
    """
    return signature + public_key


def verify_signature(
    message: bytes, public_key: bytes, signature: bytes
) -> bool:
    try:
        if len(public_key) != 64 or len(signature) != 64:
            return False
        r = int.from_bytes(signature[:32], byteorder="big")
        s = int.from_bytes(signature[32:], byteorder="big")
        if not 1 <= r < SECP256K1_ORDER:
            return False
        if not 1 <= s <= SECP256K1_ORDER // 2:
            return False
        public = PublicKey(b"\x04" + public_key)
        signature_der = secp256k1_ecdsa.cdata_to_der(
            secp256k1_ecdsa.deserialize_compact(signature)
        )
        digest = hashlib.sha256(message).digest()
        return public.verify(
            signature_der,
            digest,
            hasher=None,
        )
    except (AssertionError, TypeError, ValueError):
        return False


def deserialize_unlocking_script(unlocking_script: bytes) -> dict:
    if not isinstance(unlocking_script, bytes) or len(unlocking_script) != 128:
        raise ValueError("Unlocking script must be 128 bytes.")
    script_hex = unlocking_script.hex()
    pub_key = script_hex[:128]
    signature = script_hex[128:]

    public_key_bytes = bytes.fromhex(pub_key)
    verifying_key = PublicKey(b"\x04" + public_key_bytes)

    return {
        "signature": signature,
        "public_key": pub_key,
        "address": pubkey_to_address(verifying_key.format(compressed=True)),
    }


def is_valid_unlocking_script(
    unlocking_script: bytes,
    transaction_serialized: Union[str, bytes],
    from_address: str,
) -> bool:
    try:
        script_data = deserialize_unlocking_script(unlocking_script)
    except (binascii.Error, TypeError, ValueError):
        return False

    if script_data["address"] != from_address:
        return False

    message = _canonical_transaction_bytes(transaction_serialized)

    try:
        return verify_signature(
            message=message,
            public_key=bytes.fromhex(script_data["public_key"]),
            signature=bytes.fromhex(script_data["signature"]),
        )
    except (AssertionError, binascii.Error, ValueError):
        return False


def _canonical_transaction_bytes(serialized: Union[str, bytes]) -> bytes:
    """Accept canonical bytes and legacy hex-string callers."""
    if isinstance(serialized, bytes):
        return serialized
    try:
        return bytes.fromhex(serialized)
    except ValueError:
        return serialized.encode()


def sign_transaction(
    private_key: bytes, transaction_serialized: Union[str, bytes]
) -> bytes:
    signing_key = bytes_to_signing_key(private_key=private_key)
    public_key = signing_key.public_key.format(compressed=False)[1:]
    digest = hashlib.sha256(
        _canonical_transaction_bytes(transaction_serialized)
    ).digest()
    signature_der = signing_key.sign(digest, hasher=None)
    signature = secp256k1_ecdsa.serialize_compact(
        secp256k1_ecdsa.der_to_cdata(signature_der)
    )

    return public_key + signature
