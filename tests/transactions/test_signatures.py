import ecdsa
from luracoin.config import Config
from luracoin.transactions import (
    OutPoint,
    Transaction,
    TxIn,
    TxOut,
    transaction_chainstate_serialise,
    transaction_chainstate_deserialise,
    build_message,
    build_script_sig,
    verify_signature,
    is_valid_unlocking_script,
    deserialize_unlocking_script,
    sign_transaction,
)
from luracoin.wallet import build_p2pkh, pubkey_to_address, address_to_pubkey
from tests.constants import TRANSACTION6, COINBASE2, COINBASE1
from tests.wallet.constants import PUBLIC_KEY_1, PRIVATE_KEY_1, ADDRESS_1
from luracoin.helpers import bytes_to_signing_key


def test_deserialize_unlocking_script():
    unlocking_script = (
        "8076dcafb25fe499ac8614e811a30e50d995fc80bd38ad9d2d6c73a3dbb6f8487926"
        "37cb9566b43671b4374ef055acfcfda5268461f4e95449d4ad9858891fadff805c44"
        "0bc46d316dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1eab11c4af"
        "165e4ce3eb0652f8d937620804fe15201c00a7466f56237810988db1"
    )

    expected = {
        "signature": (
            "76dcafb25fe499ac8614e811a30e50d995fc80bd38ad9d2d6c73a3dbb6f84879"
            "2637cb9566b43671b4374ef055acfcfda5268461f4e95449d4ad9858891fadff",
        ),
        "public_key": (
            "5c440bc46d316dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1e"
            "ab11c4af165e4ce3eb0652f8d937620804fe15201c00a7466f56237810988db1",
        ),
    }

    assert sorted(deserialize_unlocking_script(unlocking_script)) == sorted(
        expected
    )


def test_transaction_signature_and_unlocking_script(blockchain):
    private_key = PRIVATE_KEY_1
    expected_address = ADDRESS_1
    outpoint = OutPoint(COINBASE1.id, 1)
    expected_public_key = PUBLIC_KEY_1
    signature = sign_transaction(private_key=private_key, outpoint=outpoint)

    private_key = bytes_to_signing_key(private_key=private_key)
    vk = private_key.get_verifying_key()
    public_key = vk.to_string().hex()

    assert public_key == expected_public_key
    assert pubkey_to_address(vk.to_string()) == expected_address

    unlocking_script = build_script_sig(
        signature=signature.hex(), public_key=public_key
    )

    assert is_valid_unlocking_script(
        unlocking_script=unlocking_script, outpoint=outpoint
    )
