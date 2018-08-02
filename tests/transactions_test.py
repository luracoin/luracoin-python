import sys, os, shutil
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from luracoin.blocks import get_blk_file_size, next_blk_file, Block, serialize_block, add_block_to_chain
from luracoin.blocks import blk_to_list
from luracoin.transactions import TxOut, TxIn, UnspentTxOut, Transaction, OutPoint, deserialize_transaction, build_p2pkh
from luracoin.transactions import add_tx_to_chainstate, read_tx_from_chainstate, remove_tx_from_chainstate
from luracoin.config import Config
import unittest
import plyvel
import json

class TransactionsTest(unittest.TestCase):
    
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

    def tearDown(self):
        folder = Config.DATA_DIR
        if os.path.exists(folder):
            shutil.rmtree(folder)

    def test_chainstate(self):
        tx = Transaction(
            version=1,
            txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)],
            txouts=[
                TxOut(value=3000000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS')),
                TxOut(value=1500000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS')),
                TxOut(value=500000000, to_address=build_p2pkh('1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS'))
            ],
            locktime=None
        )
        add_tx_to_chainstate(tx, 0)

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        tx_info_zero = read_tx_from_chainstate(db.get(b'c' + tx.id.encode() + str(0).encode()).decode())
        tx_info_one = read_tx_from_chainstate(db.get(b'c' + tx.id.encode() + str(1).encode()).decode())
        tx_info_two = read_tx_from_chainstate(db.get(b'c' + tx.id.encode() + str(2).encode()).decode())
        db.close()

        self.assertEqual(tx_info_zero['version'], 1)
        self.assertEqual(tx_info_zero['coinbase'], 1)
        self.assertEqual(tx_info_zero['height'], 0)
        self.assertEqual(tx_info_zero['output'], "005ed0b20000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac")
        self.assertEqual(tx_info_one['version'], 1)
        self.assertEqual(tx_info_one['coinbase'], 1)
        self.assertEqual(tx_info_one['height'], 0)
        self.assertEqual(tx_info_one['output'], "002f68590000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac")
        self.assertEqual(tx_info_two['version'], 1)
        self.assertEqual(tx_info_two['coinbase'], 1)
        self.assertEqual(tx_info_two['height'], 0)
        self.assertEqual(tx_info_two['output'], "0065cd1d0000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac")


        tx2 = Transaction(
            version=1,
            txins=[TxIn(to_spend=OutPoint(tx.id, 0), unlock_sig='test', sequence=0)],
            txouts=[
                TxOut(value=76000000, to_address=build_p2pkh('191erRsTQeJMKGbeCY5SdFfS7QCTdRDHik')),
                TxOut(value=21000000, to_address=build_p2pkh('191erRsTQeJMKGbeCY5SdFfS7QCTdRDHik'))
            ],
            locktime=None
        )
        add_tx_to_chainstate(tx2, 1)

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        tx_info_zero = read_tx_from_chainstate(db.get(b'c' + tx2.id.encode() + str(0).encode()).decode())
        tx_info_one = read_tx_from_chainstate(db.get(b'c' + tx2.id.encode() + str(1).encode()).decode())
        db.close()

        self.assertEqual(tx_info_zero['version'], 1)
        self.assertEqual(tx_info_zero['coinbase'], 0)
        self.assertEqual(tx_info_zero['height'], 1)
        self.assertEqual(tx_info_zero['output'], "00ab87040000000076a9150057e09a8cea5300ca102f0a11108fd4908f6aa95988ac")

        self.assertEqual(tx_info_one['version'], 1)
        self.assertEqual(tx_info_one['coinbase'], 0)
        self.assertEqual(tx_info_one['height'], 1)
        self.assertEqual(tx_info_one['output'], "406f40010000000076a9150057e09a8cea5300ca102f0a11108fd4908f6aa95988ac")


        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        info1 = {}
        for key, value in db:
            info1[key.decode()] = value.decode()
        info1['size'] = len(info1)
        db.close()
        
        remove_tx_from_chainstate("27b397b0657ac7410930be64e074219cdcfa88ef5e5b011027b38e6b5acda126", 0)
        remove_tx_from_chainstate("c2821034a332fad997e38281f8d9d6ac765171ac41f9c761f9d0cc54e02a17ee", 1)

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        info2 = {}
        for key, value in db:
            info2[key.decode()] = value.decode()
        info2['size'] = len(info2)
        db.close()

        self.assertEqual(info1['size'] - 2, info2['size'])



if __name__ == '__main__':
    unittest.main()
