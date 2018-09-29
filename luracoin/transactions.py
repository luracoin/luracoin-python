from typing import Iterable, NamedTuple, Union
import logging
from .config import Config
import os
from .helpers import sha256d, var_int, get_current_height
from .wallet import address_to_pubkey
from .pow import mining_reward
from .blockchain import OutPoint, TxIn, TxOut, UnspentTxOut, Transaction
import binascii
import plyvel
import json


logging.basicConfig(
    level=getattr(logging, os.environ.get('TC_LOG_LEVEL', 'INFO')),
    format='[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def validate_tx(tx):
    """
    Validate a transaction. For a transaction to be valid it has to follow these conditions:
    - Value is less than the total supply.
    - Tx size is less than the block size limit.
    - Value has to be equal or less than the spending transaction
    - Valid unlocking code
    """
    if not tx.txins or not tx.txouts:
        return False

    total_value = 0
    for to in tx.txouts:
        total_value = total_value + to.value

    if tx.is_coinbase and total_value > (mining_reward() * Config.BELUSHIS_PER_COIN):
        return False

    if not tx.is_coinbase:
        total_to_spend = 9999999999999
        for ti in tx.txins:
            total_to_spend = total_to_spend + 0

        if total_value > Config.MAX_MONEY:
            return False

        if total_value > total_to_spend:
            return False

        # VALIDATE SIGNATURE HERE

    return True


def validate_signature(tx_input):
    # WIP
    # P2PKH:
    # [PUB_KEY][SIGNATURE]<DUP><HASH160>[ADDRESS]<EQUALVERIFY><CHECKSIG>

    # Get the unlocking script.
    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    try:
        tx_info = read_tx_from_chainstate(
            db.get(b'c' + tx_input.to_spend.txid.encode() + str(tx_input.to_spend.txout_idx).encode()).decode()
        )
    except AttributeError:
        return False
    finally:
        db.close()

    unlocking_script = tx_info['output'][16:]
    stack = []
    working_stock = []

    acum = 0
    while acum < len(unlocking_script):
        print(unlocking_script[acum:acum+2])
        acum += 2

    #print("\n===============")
    #print(unlocking_script)
    #print("===============\n")



def build_message(to_spend, pub_key):
    """
    TODO: INSECURE, HAS TO BE IMPROVE
    """
    return sha256d(str(to_spend.txid) + str(to_spend.txout_idx) + pub_key)


def build_script_sig(signature, pub_key):
    """
    <VARINT>SIGNATURE<VARINT>PUBLIC_KEY
    """
    count_signature = len(signature) / 2
    count_signature = int(count_signature).to_bytes(1, byteorder='little', signed=False).hex()
    count_pub_key = len(pub_key) / 2
    count_pub_key = int(count_pub_key).to_bytes(1, byteorder='little', signed=False).hex()
    return str(count_signature) + signature + str(count_pub_key) + pub_key


def build_p2pkh(address: str):
    """
    We have to provide a signature and the original Public Key.
    <OP_DUP>: (0x76) pushes a copy of the topmost stack item on to the stack.
    <OP_HASH160>: (0xa9) consumes the topmost item on the stack, computes the RIPEMD160(SHA256()) 
        hash of that item, and pushes that hash onto the stack.
    <OP_EQUAL>: (0x87) consumes the top two items on the stack, compares them, and pushes true 
        onto the stack if they are the same, false if not.
    <OP_VERIFY>: (0x69) consumes the topmost item on the stack. If that item is zero (false) it 
        terminates the script in failure.
    <OP_EQUALVERIFY>: (0x88) runs OP_EQUAL and then OP_VERIFY in sequence.
    <OP_CHECKSIG>: (0xac) consumes a signature and a full public key, and pushes true onto the 
        stack if the transaction data specified by the SIGHASH flag was converted into 
        the signature using the same ECDSA private key that generated the public key. 
        Otherwise, it pushes false onto the stack.

    If the byte is < 0x4b (75) it means that is data to push into the STACK
    """
    pub_key_hash = address_to_pubkey(address)
    count_push = len(pub_key_hash) / 2
    count_push = int(count_push).to_bytes(1, byteorder='little', signed=False).hex()

    # "<OP_DUP><OP_HASH160>" + count_push + pub_key_hash + "<OP_EQUALVERIFY><OP_CHECKSIG>"
    script = "76a9" + count_push + pub_key_hash + "88ac"
    return script


def search_utxo(address: str):
    """
    Search all available UTXO of an address:

    :param address: Luracoin Address
    :return: List with all UTXO
    """
    pub_key = address_to_pubkey(address)
    utxo = {}

    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    for key, value in db:
        if pub_key in value.decode():
            utxo[key.decode()] = value.decode()

    db.close()
    return utxo


def utxo_valid(tx_id: str, vout: int):
    """
    Checks if a UTXO is valid to spend. For now the only reason a UTXO is invalid would be
    because it's a coinbase transactions and it was created less than 50 blocks ago.

    :param tx_id: Transaction ID
    :param vout: Number of output
    :return: Boolean
    """
    valid = True

    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    tx_info = read_tx_from_chainstate(db.get(b'c' + tx_id.encode() + str(vout).encode()).decode())
    db.close()

    if tx_info['coinbase'] == 1 and tx_info['height'] > get_current_height() - 50:
        valid = False

    return valid


def utxo_value(tx_id: str, vout: int):
    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    tx_info = read_tx_from_chainstate(db.get(b'c' + tx_id.encode() + str(vout).encode()).decode())
    db.close()

    return int.from_bytes(binascii.unhexlify(tx_info['output'][:16]), byteorder='little')


def remove_tx_from_chainstate(tx, vout):
    """
    Remove UTXO from the chainstate.

    :param tx: Transaction ID
    :param vout: Which output
    """
    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    db.delete(b'c' + tx.encode() + str(vout).encode())
    db.close()


def add_tx_to_chainstate(tx, height: int):
    """
    Add a transaction to the chainstate. Inside the chainstate database, the following 
    key/value pairs are stored:

    'c' + 32-byte transaction hash -> unspent transaction output record for that transaction. 
    These records are only present for transactions that have at least one unspent output left. 
    Each record stores:
        The version of the transaction.
        Whether the transaction was a coinbase or not.
        Which height block contains the transaction.
        Which outputs of that transaction are unspent.
        The scriptPubKey and amount for those unspent outputs.

        [ TX Version ][ COINBASE ][ BLOCK HEIGHT ][ NUM OUTPUTS ][∞][ OUTPUT LENGHT ][ OUTPUT ]
              ^            ^             ^              ^                 ^
           4 bytes      1 byte        4 bytes        VARINT             VARINT

    'B' -> 32-byte block hash: the block hash up to which the database represents the unspent 
    transaction outputs
    """
    for i, o in enumerate(tx.txouts):
        version = tx.version.to_bytes(1, byteorder='little', signed=False).hex()
        coinbase = tx.is_coinbase
        if coinbase:
            coinbase = int(1).to_bytes(1, byteorder='little', signed=False).hex()
        else:
            coinbase = int(0).to_bytes(1, byteorder='little', signed=False).hex()
        h = int(height).to_bytes(4, byteorder='little', signed=False).hex()
        output_content = o.value.to_bytes(8, byteorder='little', signed=False).hex() + o.to_address

        outputs = version + coinbase + h + output_content

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        db.put(b'c' + tx.id.encode() + str(i).encode(), outputs.encode())
        db.close()


def read_tx_from_chainstate(tx):
    """
    Read a transaction from the LevelDB Chainstate. And returns a Dictionary with
    all the information.
    """
    tx_info = {
        'version': int.from_bytes(binascii.unhexlify(tx[0:2]), byteorder='little'),
        'coinbase': int.from_bytes(binascii.unhexlify(tx[2:4]), byteorder='little'),
        'height': int.from_bytes(binascii.unhexlify(tx[4:12]), byteorder='little'),
        'output': tx[12:]
    }

    #print(json.dumps(tx_info, indent=4))
    return tx_info
