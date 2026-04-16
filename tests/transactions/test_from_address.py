import pytest
from binascii import unhexlify
from luracoin.transactions import Transaction, is_valid_unlocking_script
from luracoin.config import Config
from luracoin.chain import Chain
from luracoin.exceptions import TransactionNotValid
from luracoin import errors
from tests.constants import WALLET_1, WALLET_2, WALLET_3


# ---------------------------------------------------------------------------
# is_valid_unlocking_script: from_address is now required (no None default)
# ---------------------------------------------------------------------------

def test_is_valid_unlocking_script_requires_from_address():
    """
    from_address must be a required parameter. Calling without it
    should raise TypeError.
    """
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    with pytest.raises(TypeError):
        is_valid_unlocking_script(
            unlocking_script=tx.unlock_sig,
            transaction_serialized=tx.serialize(to_sign=True).hex(),
            # from_address omitted -- must raise TypeError
        )


# ---------------------------------------------------------------------------
# Transaction: from_address field
# ---------------------------------------------------------------------------

def test_transaction_has_from_address():
    """Transaction must accept and store from_address."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    assert tx.from_address == WALLET_1["address"]


def test_coinbase_transaction_from_address_is_zeros():
    """Coinbase transactions use '0' * 34 as from_address (no sender)."""
    tx = Transaction(
        chain=1, nonce=1, fee=0, value=50_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.is_coinbase is True
    assert tx.from_address == "0" * 34


# ---------------------------------------------------------------------------
# Serialization round-trip with from_address
# ---------------------------------------------------------------------------

def test_serialize_deserialize_with_from_address():
    """from_address must survive serialize -> deserialize round-trip."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )

    serialized = tx.serialize()
    tx2 = Transaction()
    tx2.deserialize(serialized)

    assert tx2.from_address == WALLET_1["address"]
    assert tx2.to_address == WALLET_2["address"]
    assert tx2.chain == 1
    assert tx2.value == 5_000_000


# ---------------------------------------------------------------------------
# validate_fields: from_address validation
# ---------------------------------------------------------------------------

def test_validate_fields_rejects_missing_from_address():
    """Non-coinbase transaction without from_address must be invalid."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    # from_address is None
    assert tx.validate_fields() is False


def test_validate_fields_rejects_wrong_length_from_address():
    """from_address must be exactly 34 characters."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address="too_short",
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.validate_fields() is False


def test_validate_fields_accepts_valid_from_address():
    """Valid 34-char from_address passes field validation."""
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.validate_fields() is True


def test_validate_fields_accepts_coinbase_zeros_from_address():
    """Coinbase from_address of '0' * 34 passes field validation."""
    tx = Transaction(
        chain=1, nonce=1, fee=0, value=50_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.validate_fields() is True


# ---------------------------------------------------------------------------
# validate(): signature must match from_address for non-coinbase
# ---------------------------------------------------------------------------

def test_validate_non_coinbase_checks_from_address_matches_signer():
    """
    The core security fix: validate() must verify that the public key
    in unlock_sig derives to from_address. If someone signs with WALLET_1
    but claims from_address=WALLET_2, validation MUST fail.
    """
    chain = Chain()
    chain.set_account(WALLET_2["address"], {"balance": 100_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_2["address"],  # WRONG: claiming to be WALLET_2
        to_address=WALLET_3["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))  # but signed by WALLET_1

    assert tx.validate() is False


def test_validate_non_coinbase_passes_when_signer_matches():
    """When from_address matches the actual signer, validation passes."""
    chain = Chain()
    chain.set_account(WALLET_1["address"], {"balance": 100_000_000, "nonce": 0})

    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
    )
    tx = tx.sign(unhexlify(WALLET_1["private_key"]))

    assert tx.validate() is True


def test_validate_coinbase_skips_signature_check():
    """Coinbase transactions skip the signature/from_address check entirely."""
    tx = Transaction(
        chain=1, nonce=1, fee=0, value=50_000,
        from_address="0" * 34,
        to_address=WALLET_1["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    assert tx.validate() is True


# ---------------------------------------------------------------------------
# json() includes from_address
# ---------------------------------------------------------------------------

def test_json_includes_from_address():
    tx = Transaction(
        chain=1, nonce=1, fee=100, value=5_000_000,
        from_address=WALLET_1["address"],
        to_address=WALLET_2["address"],
        unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
    )
    j = tx.json()
    assert "from_address" in j
    assert j["from_address"] == WALLET_1["address"]
