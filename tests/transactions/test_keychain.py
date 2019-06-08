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
from luracoin.helpers import bytes_to_signing_key


def test_transaction_chainstate_serialise(blockchain) -> None:  # type: ignore
    serialised_chainstate_1 = transaction_chainstate_serialise(
        transaction=TRANSACTION6, output=TRANSACTION6.txouts[0], block_height=1
    )
    assert serialised_chainstate_1 == (
        "010001000000b0ad0100000000000044d27de0e2f8e87f26beaf3cc727f1a642a09af3"
    )

    serialised_chainstate_2 = transaction_chainstate_serialise(
        transaction=TRANSACTION6, output=TRANSACTION6.txouts[1], block_height=1
    )
    assert serialised_chainstate_2 == (
        "010001000000f049020000000000002a35a40188d3ca15da2cb5ac43c5f3add8c64b16"
    )

    serialised_chainstate_3 = transaction_chainstate_serialise(
        transaction=TRANSACTION6, output=TRANSACTION6.txouts[2], block_height=1
    )
    assert serialised_chainstate_3 == (
        "01000100000050c300000000000000d00b433df737fd3da4b2551a356d556206f2e607"
    )

    serialised_chainstate_4 = transaction_chainstate_serialise(
        transaction=TRANSACTION6, output=TRANSACTION6.txouts[3], block_height=1
    )
    assert serialised_chainstate_4 == (
        "01000100000098ab02000000000000785211d22e8c5c6bad7410b9baf99dac866a447f"
    )

    serialised_chainstate_5 = transaction_chainstate_serialise(
        transaction=COINBASE2, output=COINBASE2.txouts[0], block_height=1
    )
    assert serialised_chainstate_5 == (
        "01010100000000f2052a01000000008d3f74c5f4b7b9d3193a950986a9a16decb41550"
    )


def test_transaction_chainstate_deserialise(blockchain):  # type: ignore
    serialised_chainstate_1 = (
        "010001000000b0ad0100000000000044d27de0e2f8e87f26beaf3cc7"
        "27f1a642a09af3"
    )
    transaction1 = transaction_chainstate_deserialise(serialised_chainstate_1)
    assert transaction1["version"] == 1
    assert transaction1["is_coinbase"] == 0
    assert transaction1["height"] == 1
    assert transaction1["value"] == 110_000
    assert (
        transaction1["to_address"]
        == "0044d27de0e2f8e87f26beaf3cc727f1a642a09af3"
    )

    serialised_chainstate_2 = (
        "010001000000f049020000000000002a35a40188d3ca15da2cb5ac43c"
        "5f3add8c64b16"
    )
    transaction2 = transaction_chainstate_deserialise(serialised_chainstate_2)
    assert transaction2["version"] == 1
    assert transaction2["is_coinbase"] == 0
    assert transaction2["height"] == 1
    assert transaction2["value"] == 150_000
    assert (
        transaction2["to_address"]
        == "002a35a40188d3ca15da2cb5ac43c5f3add8c64b16"
    )

    serialised_chainstate_3 = (
        "01000100000050c300000000000000d00b433df737fd3da4b2551a35"
        "6d556206f2e607"
    )
    transaction3 = transaction_chainstate_deserialise(serialised_chainstate_3)
    assert transaction3["version"] == 1
    assert transaction3["is_coinbase"] == 0
    assert transaction3["height"] == 1
    assert transaction3["value"] == 50000
    assert (
        transaction3["to_address"]
        == "00d00b433df737fd3da4b2551a356d556206f2e607"
    )

    serialised_chainstate_4 = (
        "01000100000098ab02000000000000785211d22e8c5c6bad7410b9ba"
        "f99dac866a447f"
    )
    transaction4 = transaction_chainstate_deserialise(serialised_chainstate_4)
    assert transaction4["version"] == 1
    assert transaction4["is_coinbase"] == 0
    assert transaction4["height"] == 1
    assert transaction4["value"] == 175_000
    assert (
        transaction4["to_address"]
        == "00785211d22e8c5c6bad7410b9baf99dac866a447f"
    )

    serialised_chainstate_5 = (
        "01010100000000f2052a01000000008d3f74c5f4b7b9d3193a950986"
        "a9a16decb41550"
    )
    transaction5 = transaction_chainstate_deserialise(serialised_chainstate_5)
    assert transaction5["version"] == 1
    assert transaction5["is_coinbase"] == 1
    assert transaction5["height"] == 1
    assert transaction5["value"] == 5_000_000_000
    assert (
        transaction5["to_address"]
        == "008d3f74c5f4b7b9d3193a950986a9a16decb41550"
    )
