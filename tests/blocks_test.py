import sys, os, shutil
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from luracoin.blocks import get_blk_file_size, next_blk_file, Block, serialize_block, add_block_to_chain
from luracoin.blocks import blk_to_list, find_block_in_file, deserialize_block
from luracoin.transactions import TxOut, TxIn, UnspentTxOut, Transaction, OutPoint, deserialize_transaction
from luracoin.transactions import build_message, build_p2pkh, build_script_sig
from luracoin.config import Config
from luracoin.wallet import get_wallet
import unittest

class BlocksTest(unittest.TestCase):

    maxDiff = None
    
    def setUp(self):
        Config.DATA_DIR = Config.BASE_DIR + '/tests/data/'
        Config.BLOCKS_DIR = Config.DATA_DIR + 'blocks/'

        folder = Config.BLOCKS_DIR
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)

        # ================== GENESIS BLOCK ==================

        tx_out = TxOut(value=5000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)

        tx = Transaction(
            version=1,
            txins=[tx_in],
            txouts=[tx_out],
            locktime=None
        )

        genesis_block = Block(
            version=1,
            prev_block_hash=0,
            timestamp=1501821412,
            bits=24,
            nonce=10126761,
            txns=[tx])

        serialized_block = serialize_block(genesis_block)

        add_block_to_chain(serialized_block)

        # Public_key
        keys = get_wallet()
        public_key = "79b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee"
        spend_msg = build_message(OutPoint(tx.id, 0), public_key)
        sig = keys[0].sign(spend_msg.encode())

        tx_out = TxOut(value=5000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig='1', sequence=0)
        tx = Transaction(version=1, txins=[tx_in], txouts=[tx_out], locktime=None)

        tx_out1 = TxOut(value=1000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_out2 = TxOut(value=2000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_out3 = TxOut(value=2000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(tx.id, 0), unlock_sig=build_script_sig(sig.hex(), public_key), sequence=0)
        tx1 = Transaction(version=1, txins=[tx_in], txouts=[tx_out1, tx_out2, tx_out3], locktime=None)

        block1 = Block(
            version=1,
            prev_block_hash=genesis_block.id,
            timestamp=1501821412,
            bits=24,
            nonce=10126761,
            txns=[tx, tx1])

        serialized_block = serialize_block(block1)

        add_block_to_chain(serialized_block)


    def tearDown(self):
        folder = Config.DATA_DIR
        if os.path.exists(folder):
            shutil.rmtree(folder)

    def test_blk_to_list(self):
        self.assertEqual(len(blk_to_list('000000', True)), 2)
        self.assertEqual(len(blk_to_list('000000')), 2)

    def test_next_blk_file(self):
        self.assertEqual(next_blk_file('000000'), '000001')
        self.assertEqual(next_blk_file('000009'), '000010')
        self.assertEqual(next_blk_file('000020'), '000021')
        self.assertEqual(next_blk_file('000099'), '000100')

    def test_find_block_in_file(self):
        #print("Finding block")
        #print(find_block_in_file(blk_height=1, blk_file='000000'))
        pass
    
    def test_serialize_block(self):
        keys = get_wallet()
        public_key = "79b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee"
        spend_msg = build_message(OutPoint("27b397b0657ac7410930be64e074219cdcfa88ef5e5b011027b38e6b5acda126", 0), public_key)
        sig = keys[0].sign(spend_msg.encode())
        script_sig = build_script_sig(sig.hex(), public_key)

        tx_out = TxOut(value=5000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(0, -1), unlock_sig='1', sequence=0)
        tx = Transaction(version=1, txins=[tx_in], txouts=[tx_out], locktime=None)

        tx_out1 = TxOut(value=1000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_out2 = TxOut(value=2000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_out3 = TxOut(value=2000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
        tx_in = TxIn(to_spend=OutPoint(tx.id, 0), unlock_sig=script_sig, sequence=0)
        tx1 = Transaction(version=1, txins=[tx_in], txouts=[tx_out1, tx_out2, tx_out3], locktime=None)

        block1 = Block(
            version=1,
            prev_block_hash="56254692955540c5e15ccc5f374c507e785f8c87ddd89b22279556153cf34061",
            timestamp=1501821412,
            bits=24,
            nonce=10126761,
            txns=[tx, tx1])

        serialized_block = serialize_block(block1)
        block1_new = deserialize_block(serialized_block)

        self.assertEqual(block1_new.version, block1.version)
        self.assertEqual(block1_new.timestamp, block1.timestamp)
        self.assertEqual(block1_new.bits, block1.bits)
        self.assertEqual(block1_new.nonce, block1.nonce)

        self.assertEqual(block1_new.txns[0].version, block1.txns[0].version)
        self.assertEqual(block1_new.txns[0].locktime, block1.txns[0].locktime)
        self.assertEqual(block1_new.txns[0].txins[0].to_spend, block1.txns[0].txins[0].to_spend)
        self.assertEqual(block1_new.txns[0].txins[0].unlock_sig, block1.txns[0].txins[0].unlock_sig)
        self.assertEqual(block1_new.txns[0].txins[0].sequence, block1.txns[0].txins[0].sequence)
        self.assertEqual(block1_new.txns[0].txouts[0].value, block1.txns[0].txouts[0].value)
        self.assertEqual(block1_new.txns[0].txouts[0].to_address, block1.txns[0].txouts[0].to_address)
        self.assertEqual(block1_new.txns[0].id, block1.txns[0].id)

        self.assertEqual(block1_new.txns[1].version, block1.txns[1].version)
        self.assertEqual(block1_new.txns[1].locktime, block1.txns[1].locktime)
        self.assertEqual(block1_new.txns[1].txins[0].to_spend, block1.txns[1].txins[0].to_spend)
        self.assertEqual(block1_new.txns[1].txins[0].unlock_sig, block1.txns[1].txins[0].unlock_sig)
        self.assertEqual(block1_new.txns[1].txins[0].sequence, block1.txns[1].txins[0].sequence)
        self.assertEqual(block1_new.txns[1].txouts[0].value, block1.txns[1].txouts[0].value)
        self.assertEqual(block1_new.txns[1].txouts[0].to_address, block1.txns[1].txouts[0].to_address)
        self.assertEqual(block1_new.txns[1].id, block1.txns[1].id)

        self.assertEqual(block1_new.prev_block_hash, block1.prev_block_hash)


if __name__ == '__main__':
    unittest.main()
