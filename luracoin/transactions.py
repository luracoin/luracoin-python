from typing import Iterable, NamedTuple, Union
import logging
from .config import Config
import os
from .helpers import sha256d, var_int, get_current_height
from .wallet import address_to_pubkey
import binascii
import plyvel
import json


logging.basicConfig(
    level=getattr(logging, os.environ.get('TC_LOG_LEVEL', 'INFO')),
    format='[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


# Used to represent the specific output within a transaction.
OutPoint = NamedTuple('OutPoint', [('txid', str), ('txout_idx', int)])


class TxIn(NamedTuple):
    """Inputs to a Transaction."""
    # A reference to the output we're spending. This is None for coinbase
    # transactions.
    to_spend: Union[OutPoint, None]

    # The (signature, pubkey) pair which unlocks the TxOut for spending.
    unlock_sig: bytes
    #unlock_pk: bytes

    # A sender-defined sequence number which allows us replacement of the txn
    # if desired.
    sequence: int


class TxOut(NamedTuple):
    """Outputs from a Transaction."""
    # The number of Belushis this awards.
    value: int

    # The public key of the owner of this Txn.
    to_address: str


class UnspentTxOut(NamedTuple):
    value: int
    to_address: str

    # The ID of the transaction this output belongs to.
    txid: str
    txout_idx: int

    # Did this TxOut from from a coinbase transaction?
    is_coinbase: bool

    # The blockchain height this TxOut was included in the chain.
    height: int

    @property
    def outpoint(self): return OutPoint(self.txid, self.txout_idx)


class Transaction(NamedTuple):
    # Which version of transaction data structure we're using.
    version: int

    txins: Iterable[TxIn]
    txouts: Iterable[TxOut]

    # The block number or timestamp at which this transaction is unlocked.
    # < 500000000: Block number at which this transaction is unlocked.
    # >= 500000000: UNIX timestamp at which this transaction is unlocked.
    locktime: int = None

    @property
    def is_coinbase(self) -> bool:
        return len(self.txins) == 1 and str(self.txins[0].to_spend.txid) == '0'

    @property
    def id(self) -> str:
        msg = ''
        for x in self.txins:
            msg = msg + str(x.to_spend.txid) + str(x.to_spend.txout_idx) + str(x.unlock_sig) + str(x.sequence)
        for y in self.txouts:
            msg = msg + str(y.value) + str(y.to_address)

        tx_id = sha256d(msg)
        return tx_id

    def validate_basics(self, as_coinbase=False):
        if (not self.txouts) or (not self.txins and not as_coinbase):
            raise TxnValidationError('Missing txouts or txins')

        if len(serialize(self)) > Config.MAX_BLOCK_SERIALIZED_SIZE:
            raise TxnValidationError('Too large')

        if sum(t.value for t in self.txouts) > Config.MAX_MONEY:
            raise TxnValidationError('Spend value too high')

    def make_msg(self):
        '''
        TODO: Improve the message.
        bitcoin.stackexchange.com/questions/37093/what-goes-in-to-the-message-of-a-transaction-signature
        '''
        return self.id

    def serialize_transaction(self):
        # Version (2 bytes)
        # Number Inputs (2 bytes)
        total = ''

        # Convert to little endian
        version = self.version.to_bytes(2, byteorder='little', signed=False).hex()

        # INPUTS:

        num_inputs = len(self.txins)
        if num_inputs <= 252:
            num_inputs = num_inputs.to_bytes(1, byteorder='little', signed=False).hex()
        elif num_inputs <= 65535:
            num_inputs = "fd" + num_inputs.to_bytes(2, byteorder='little', signed=False).hex()
        elif num_inputs <= 4294967295:
            num_inputs = "fe" + num_inputs.to_bytes(4, byteorder='little', signed=False).hex()
        else:
            num_inputs = "ff" + num_inputs.to_bytes(8, byteorder='little', signed=False).hex()

        total = version + num_inputs

        for i in self.txins:
            tx_id = i.to_spend.txid

            if i.to_spend.txid == 0:
                tx_id = "0000000000000000000000000000000000000000000000000000000000000000"

            # Output to spent
            if i.to_spend.txout_idx == -1:
                vout = 'ffffffff'  # Index. ffffffff for Coinbase
            else:
                vout = i.to_spend.txout_idx.to_bytes(4, byteorder='little', signed=False).hex()

            # TODO:
            script_sig = i.unlock_sig
            script_sig_size = var_int(len(script_sig))  # VarInt
            sequence = i.sequence.to_bytes(4, byteorder='little', signed=False).hex()
            total = total + str(tx_id) + vout + str(script_sig_size) + script_sig + sequence

        # OUTPUTS:
        num_outputs = len(self.txouts)
        total = total + var_int(num_outputs)

        for o in self.txouts:
            # 1) Value
            # 2) ScriptPubKey Size
            # 3) ScriptPubKey
            value = o.value.to_bytes(8, byteorder='little', signed=False).hex()
            script_pub_key = o.to_address
            script_pub_key_size = var_int(len(script_pub_key))
            total = total + value + script_pub_key_size + script_pub_key

        return total


def validate_tx(tx):
    '''
    Validate a transaction. For a transaction to be valid it has to follow these conditions:
    - Value is less than the total supply.
    - Tx size is less than the block size limit.
    - Txin and Txout not empty
    - Value has to be equal or less than the spending transaction
    - Valid unlocking code
    '''
    return True


def build_message(to_spend, pub_key):
    '''
    TODO: INSECURE, HAS TO BE IMPROVE
    '''
    return sha256d(str(to_spend.txid) + str(to_spend.txout_idx) + pub_key)


def build_script_sig(signature, pub_key):
    '''
    <VARINT>SIGNATURE<VARINT>PUBLIC_KEY
    '''
    count_signature = len(signature) / 2
    count_signature = int(count_signature).to_bytes(1, byteorder='little', signed=False).hex()
    count_pub_key = len(pub_key) / 2
    count_pub_key = int(count_pub_key).to_bytes(1, byteorder='little', signed=False).hex()
    return str(count_signature) + signature + str(count_pub_key) + pub_key


def build_p2pkh(address: str):
    '''
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
    '''
    pub_key_hash = address_to_pubkey(address)
    count_push = len(pub_key_hash) / 2
    count_push = int(count_push).to_bytes(1, byteorder='little', signed=False).hex()

    # "<OP_DUP><OP_HASH160>" + count_push + pub_key_hash + "<OP_EQUALVERIFY><OP_CHECKSIG>"
    script = "76a9" + count_push + pub_key_hash + "88ac"
    return script


def search_utxo(address: str):
    '''
    Search all available UTXO of an address:

    :param address: Luracoin Address
    :return: List with all UTXO
    '''
    pub_key = address_to_pubkey(address)
    utxo = {}

    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    for key, value in db:
        if pub_key in value.decode():
            utxo[key.decode()] = value.decode()

    db.close()
    return utxo


def utxo_valid(tx_id: str, vout: int):
    '''
    Checks if a UTXO is valid to spend. For now the only reason a UTXO is invalid would be
    because it's a coinbase transactions and it was created less than 50 blocks ago.

    :param tx_id: Transaction ID
    :param vout: Number of output
    :return: Boolean
    '''
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
    '''
    Remove UTXO from the chainstate.

    :param tx: Transaction ID
    :param vout: Which output
    '''
    db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
    db.delete(b'c' + tx.encode() + str(vout).encode())
    db.close()


def add_tx_to_chainstate(tx, height: int):
    '''
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
    '''
    for i, o in enumerate(tx.txouts):
        #print("Key is: " + str(i) + " and Value is: " + str(o))
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
    '''
    Read a transaction from the LevelDB Chainstate. And returns a Dictionary with
    all the information.
    '''
    tx_info = {
        'version': int.from_bytes(binascii.unhexlify(tx[0:2]), byteorder='little'),
        'coinbase': int.from_bytes(binascii.unhexlify(tx[2:4]), byteorder='little'),
        'height': int.from_bytes(binascii.unhexlify(tx[4:12]), byteorder='little'),
        'output': tx[12:]
    }

    # print(json.dumps(tx_info, indent=4))
    return tx_info


def deserialize_transaction(tx):
    '''
    TODO: REFACTOR
    '''

    transactions = []

    num_txs = tx[0:2]
    c = 2
    if num_txs == 'fd':
        num_txs = tx[c:c+4]
        c = c + 4
    elif num_txs == 'fe':
        num_txs = tx[c:c+8]
        c = c + 8
    elif num_txs == 'ff':
        num_txs = tx[c:c+16]
        c = c + 16

    num_txs = int.from_bytes(binascii.unhexlify(num_txs), byteorder='little')

    for t in range(num_txs):

        version = int.from_bytes(binascii.unhexlify(tx[c:c+4]), byteorder='little')
        c = c + 4

        transaction = Transaction(
            version=version,
            txins=[],
            txouts=[]
        )

        number_txins = tx[c:c+2]
        c = c + 2
        if number_txins == 'fd':
            number_txins = tx[c:c+4]
            c = c + 4
        elif number_txins == 'fe':
            number_txins = tx[c:c+8]
            c = c + 8
        elif number_txins == 'ff':
            number_txins = tx[c:c+16]
            c = c + 16

        number_txins = int.from_bytes(binascii.unhexlify(number_txins), byteorder='little')

        # TXIN
        for n in range(number_txins):
            # Transaction ID
            tx_id = tx[c:c+64]
            c = c + 64
            if tx_id == '0000000000000000000000000000000000000000000000000000000000000000':
                tx_id = 0

            # VOUT
            vout = tx[c:c+8]
            c = c + 8
            if vout == 'ffffffff':
                vout = -1
            else:
                vout = int.from_bytes(binascii.unhexlify(vout), byteorder='little')

            # SIGNATURE SIZE
            size_sig = tx[c:c+2]
            c = c + 2
            if size_sig == 'fd':
                size_sig = tx[c:c+4]
                c = c + 4
            elif size_sig == 'fe':
                size_sig = tx[c:c+8]
                c = c + 8
            elif size_sig == 'ff':
                size_sig = tx[c:c+16]
                c = c + 16

            size_sig = int.from_bytes(binascii.unhexlify(size_sig), byteorder='little')

            # SIGNATURE
            sig = tx[c:c+size_sig]
            c = c + size_sig

            # SEQUENCE
            sequence = tx[c:c+8]
            sequence = int.from_bytes(binascii.unhexlify(sequence), byteorder='little')

            c = c + 8

            tx_in = TxIn(
                to_spend=OutPoint(tx_id, vout),
                unlock_sig=sig,
                sequence=sequence
            )
            transaction.txins.append(tx_in)

        # TXOUT
        number_txout = tx[c:c+2]
        c = c + 2
        if number_txout == 'fd':
            number_txins = tx[c:c+4]
            c = c + 4
        elif number_txout == 'fe':
            number_txins = tx[c:c+8]
            c = c + 8
        elif number_txout == 'ff':
            number_txins = tx[c:c+16]
            c = c + 16

        number_txout = int.from_bytes(binascii.unhexlify(number_txout), byteorder='little')
        for n in range(number_txout):
            # VALUE
            value = int.from_bytes(binascii.unhexlify(tx[c:c+16]), byteorder='little')
            c = c + 16

            # SIZE SCRIPT
            size_script = tx[c:c+2]
            c = c + 2
            if size_script == 'fd':
                size_script = tx[c:c+4]
                c = c + 4
            elif size_script == 'fe':
                size_script = tx[c:c+8]
                c = c + 8
            elif size_script == 'ff':
                size_script = tx[c:c+16]
                c = c + 16

            size_script = int.from_bytes(binascii.unhexlify(size_script), byteorder='little')
            script = tx[c:c+size_script]
            c = c + size_script

            tx_out = TxOut(value=value, to_address=script)
            transaction.txouts.append(tx_out)

        transactions.append(transaction)

    return transactions
