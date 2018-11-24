from base58 import b58decode_check

from luracoin.helpers import little_endian


def address_to_pubkey(address: str) -> str:
    return b58decode_check(address).hex()


def build_p2pkh(address: str) -> str:
    """
    We have to provide a signature and the original Public Key.
    <OP_DUP>: (0x76) pushes a copy of the topmost stack item on to the stack.
    <OP_HASH160>: (0xa9) consumes the topmost item on the stack, computes the
        RIPEMD160(SHA256()) hash of that item, and pushes that hash onto the
        stack.
    <OP_EQUAL>: (0x87) consumes the top two items on the stack, compares them,
        and pushes true onto the stack if they are the same, false if not.
    <OP_VERIFY>: (0x69) consumes the topmost item on the stack. If that item
        is zero (false) it terminates the script in failure.
    <OP_EQUALVERIFY>: (0x88) runs OP_EQUAL and then OP_VERIFY in sequence.
    <OP_CHECKSIG>: (0xac) consumes a signature and a full public key, and
        pushes true onto the stack if the transaction data specified by the
        SIGHASH flag was converted into the signature using the same ECDSA
        private key that generated the public key. Otherwise, it pushes false
        onto the stack.

    If the byte is < 0x4b (75) it means that is data to push into the STACK
    """
    pub_key_hash = address_to_pubkey(address)
    count_push = little_endian(num_bytes=1, data=int(len(pub_key_hash) / 2))

    # "<OP_DUP><OP_HASH160>len_push pub_key<OP_EQUALVERIFY><OP_CHECKSIG>"
    script = "76a9" + count_push + pub_key_hash + "88ac"
    return script
