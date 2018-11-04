import binascii

from .blockchain import Block, OutPoint, Transaction, TxIn, TxOut
from .config import Config


def deserialize_block(serialized_block: str) -> Block:
    # magic = serialized_block[0:8]
    version = serialized_block[8:16]
    prev_hash = serialized_block[16:80]
    # block_hash = serialized_block[80:144]
    bits = serialized_block[144:152]
    timestamp = serialized_block[152:160]
    nonce = serialized_block[160:172]

    block = Block(
        version=int.from_bytes(
            binascii.unhexlify(version), byteorder="little"
        ),
        prev_block_hash=prev_hash,
        timestamp=int.from_bytes(
            binascii.unhexlify(timestamp), byteorder="little"
        ),
        bits=int.from_bytes(binascii.unhexlify(bits), byteorder="little"),
        nonce=int.from_bytes(binascii.unhexlify(nonce), byteorder="little"),
        txns=[],
    )

    txns = deserialize_transaction(serialized_block[172:])
    for t in txns:
        block.txns.append(t)

    return block


def deserialize_transaction(tx):
    """
    TODO: REFACTOR
    """

    transactions = []

    num_txs = tx[0:2]
    c = 2
    if num_txs == "fd":
        num_txs = tx[c : c + 4]
        c = c + 4
    elif num_txs == "fe":
        num_txs = tx[c : c + 8]
        c = c + 8
    elif num_txs == "ff":
        num_txs = tx[c : c + 16]
        c = c + 16

    num_txs = int.from_bytes(binascii.unhexlify(num_txs), byteorder="little")

    for t in range(num_txs):

        version = int.from_bytes(
            binascii.unhexlify(tx[c : c + 4]), byteorder="little"
        )
        c = c + 4

        transaction = Transaction(version=version, txins=[], txouts=[])

        number_txins = tx[c : c + 2]
        c = c + 2
        if number_txins == "fd":
            number_txins = tx[c : c + 4]
            c = c + 4
        elif number_txins == "fe":
            number_txins = tx[c : c + 8]
            c = c + 8
        elif number_txins == "ff":
            number_txins = tx[c : c + 16]
            c = c + 16

        number_txins = int.from_bytes(
            binascii.unhexlify(number_txins), byteorder="little"
        )

        # TXIN
        for n in range(number_txins):
            # Transaction ID
            tx_id = tx[c : c + 64]
            c = c + 64
            if tx_id == Config.COINBASE_TX_ID:
                tx_id = 0

            # VOUT
            vout = tx[c : c + 8]
            c = c + 8
            if vout == "ffffffff":
                vout = -1
            else:
                vout = int.from_bytes(
                    binascii.unhexlify(vout), byteorder="little"
                )

            # SIGNATURE SIZE
            size_sig = tx[c : c + 2]
            c = c + 2
            if size_sig == "fd":
                size_sig = tx[c : c + 4]
                c = c + 4
            elif size_sig == "fe":
                size_sig = tx[c : c + 8]
                c = c + 8
            elif size_sig == "ff":
                size_sig = tx[c : c + 16]
                c = c + 16

            size_sig = int.from_bytes(
                binascii.unhexlify(size_sig), byteorder="little"
            )

            # SIGNATURE
            sig = tx[c : c + size_sig]
            c = c + size_sig

            # SEQUENCE
            sequence = tx[c : c + 8]
            sequence = int.from_bytes(
                binascii.unhexlify(sequence), byteorder="little"
            )

            c = c + 8

            tx_in = TxIn(
                to_spend=OutPoint(tx_id, vout),
                unlock_sig=sig,
                sequence=sequence,
            )
            transaction.txins.append(tx_in)

        # TXOUT
        number_txout = tx[c : c + 2]
        c = c + 2
        if number_txout == "fd":
            number_txins = tx[c : c + 4]
            c = c + 4
        elif number_txout == "fe":
            number_txins = tx[c : c + 8]
            c = c + 8
        elif number_txout == "ff":
            number_txins = tx[c : c + 16]
            c = c + 16

        number_txout = int.from_bytes(
            binascii.unhexlify(number_txout), byteorder="little"
        )
        for n in range(number_txout):
            # VALUE
            value = int.from_bytes(
                binascii.unhexlify(tx[c : c + 16]), byteorder="little"
            )
            c = c + 16

            # SIZE SCRIPT
            size_script = tx[c : c + 2]
            c = c + 2
            if size_script == "fd":
                size_script = tx[c : c + 4]
                c = c + 4
            elif size_script == "fe":
                size_script = tx[c : c + 8]
                c = c + 8
            elif size_script == "ff":
                size_script = tx[c : c + 16]
                c = c + 16

            size_script = int.from_bytes(
                binascii.unhexlify(size_script), byteorder="little"
            )
            script = tx[c : c + size_script]
            c = c + size_script

            tx_out = TxOut(value=value, to_address=script)
            transaction.txouts.append(tx_out)

        transactions.append(transaction)

    return transactions
