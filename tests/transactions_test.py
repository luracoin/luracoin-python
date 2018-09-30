from luracoin.transactions import build_p2pkh, validate_signature
from luracoin.blockchain import TxOut, TxIn, Transaction, OutPoint
from luracoin.transactions import (
    add_tx_to_chainstate,
    read_tx_from_chainstate,
    remove_tx_from_chainstate,
    validate_tx
)
from luracoin.config import Config
import unittest
import plyvel

from tests.blockchain_test import LuracoinTest


class TransactionsTest(LuracoinTest):

    address1: str
    address2: str
    address3: str

    @unittest.skip("WIP")
    def test_chainstate(self) -> None:
        tx = Transaction(
            version=1,
            txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)],
            txouts=[
                TxOut(
                    value=3000000000,
                    to_address=build_p2pkh(
                        '1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS')
                ),
                TxOut(
                    value=1500000000,
                    to_address=build_p2pkh(
                        '1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS')
                ),
                TxOut(
                    value=500000000,
                    to_address=build_p2pkh(
                        '1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS')
                    )
            ],
            locktime=0
        )
        add_tx_to_chainstate(tx, 0)

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        tx_info_zero = read_tx_from_chainstate(
            db.get(b'c' + tx.id.encode() + str(0).encode()).decode())
        tx_info_one = read_tx_from_chainstate(
            db.get(b'c' + tx.id.encode() + str(1).encode()).decode())
        tx_info_two = read_tx_from_chainstate(
            db.get(b'c' + tx.id.encode() + str(2).encode()).decode())
        db.close()

        self.assertTrue(validate_tx(tx))
        self.assertEqual(tx_info_zero['version'], 1)
        self.assertEqual(tx_info_zero['coinbase'], 1)
        self.assertEqual(tx_info_zero['height'], 0)
        self.assertEqual(
            tx_info_zero['output'],
            "005ed0b20000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
            "1b88ac"
        )
        self.assertEqual(tx_info_one['version'], 1)
        self.assertEqual(tx_info_one['coinbase'], 1)
        self.assertEqual(tx_info_one['height'], 0)
        self.assertEqual(
            tx_info_one['output'],
            "002f68590000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
            "1b88ac"
        )
        self.assertEqual(tx_info_two['version'], 1)
        self.assertEqual(tx_info_two['coinbase'], 1)
        self.assertEqual(tx_info_two['height'], 0)
        self.assertEqual(
            tx_info_two['output'],
            "0065cd1d0000000076a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd"
            "1b88ac"
        )

        tx2 = Transaction(
            version=1,
            txins=[
                TxIn(
                    to_spend=OutPoint(tx.id, 0),
                    unlock_sig='test',
                    sequence=0
                )
            ],
            txouts=[
                TxOut(
                    value=76000000,
                    to_address=build_p2pkh(
                        '191erRsTQeJMKGbeCY5SdFfS7QCTdRDHik')
                ),
                TxOut(
                    value=21000000,
                    to_address=build_p2pkh(
                        '191erRsTQeJMKGbeCY5SdFfS7QCTdRDHik')
                )
            ],
            locktime=0
        )
        add_tx_to_chainstate(tx2, 1)

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        tx_info_zero = read_tx_from_chainstate(
            db.get(b'c' + tx2.id.encode() + str(0).encode()).decode())
        tx_info_one = read_tx_from_chainstate(
            db.get(b'c' + tx2.id.encode() + str(1).encode()).decode())
        db.close()

        self.assertTrue(validate_tx(tx2))
        self.assertEqual(tx_info_zero['version'], 1)
        self.assertEqual(tx_info_zero['coinbase'], 0)
        self.assertEqual(tx_info_zero['height'], 1)
        self.assertEqual(
            tx_info_zero['output'],
            "00ab87040000000076a9150057e09a8cea5300ca102f0a11108fd4908f6aa"
            "95988ac"
        )

        self.assertEqual(tx_info_one['version'], 1)
        self.assertEqual(tx_info_one['coinbase'], 0)
        self.assertEqual(tx_info_one['height'], 1)
        self.assertEqual(
            tx_info_one['output'],
            "406f40010000000076a9150057e09a8cea5300ca102f0a11108fd4908f6aa"
            "95988ac")

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        info1 = {}
        for key, value in db:
            info1[key.decode()] = value.decode()
        info1['size'] = len(info1)
        db.close()

        remove_tx_from_chainstate(
            tx="27b397b0657ac7410930be64e074219cdcfa88ef5e5b011027b38e6b5ac"
               "da126",
            vout=0
        )
        remove_tx_from_chainstate(
            tx="c2821034a332fad997e38281f8d9d6ac765171ac41f9c761f9d0cc54e0"
               "2a17ee",
            vout=1
        )

        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        info2 = {}
        for key, value in db:
            info2[key.decode()] = value.decode()
        info2['size'] = len(info2)
        db.close()

        self.assertEqual(info1['size'] - 2, info2['size'])

    def test_validate_tx(self) -> None:
        # Coinbase transaction with the correct reward
        tx_0 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)
            ],
            txouts=[
                TxOut(value=5000000000, to_address=build_p2pkh(self.address1))
            ]
        )
        self.assertTrue(validate_tx(tx_0))

        # Empty TXIN
        tx_test_1 = Transaction(
            version=1, locktime=0, txins=[],
            txouts=[
                TxOut(value=3000000000, to_address=build_p2pkh(self.address1))
            ],
        )
        self.assertFalse(validate_tx(tx_test_1))

        # Empty TXOUT
        tx_test_2 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)
            ],
            txouts=[],
        )
        self.assertFalse(validate_tx(tx_test_2))

        # Is a Coinbase transaction with a reward greater than 50 LURA
        tx_test_3 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)
            ],
            txouts=[
                TxOut(value=5100000000, to_address=build_p2pkh(self.address1))
            ],
        )
        self.assertFalse(validate_tx(tx_test_3))

        # Is a Coinbase transaction with a reward greater than 50 LURA
        tx_test_4 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)
            ],
            txouts=[
                TxOut(
                    value=4900000000, to_address=build_p2pkh(self.address1)
                ),
                TxOut(value=200000000, to_address=build_p2pkh(self.address1)),
            ]
        )
        self.assertFalse(validate_tx(tx_test_4))

        # The Amount is greater than the total supply
        tx_test_5 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(
                    to_spend=OutPoint(self.tx0, 0),
                    unlock_sig='0',
                    sequence=0
                )
            ],
            txouts=[
                TxOut(
                    value=2100004900000000,
                    to_address=build_p2pkh(self.address1)
                ),
                TxOut(value=200000000, to_address=build_p2pkh(self.address1)),
            ]
        )
        self.assertFalse(validate_tx(tx_test_5))

    def test_validate_signature(self) -> None:
        db = plyvel.DB(Config.DATA_DIR + 'chainstate', create_if_missing=True)
        info = {}
        for key, value in db:
            info[key.decode()] = value.decode()

        info['size'] = len(info)
        db.close()

        v1 = validate_signature(
            TxIn(
                to_spend=OutPoint(self.tx1.id, 0),
                unlock_sig='-', sequence=0))
        self.assertFalse(v1)
        # Trabajar en validar la transaccion.

    @unittest.skip("WIP")
    def test_todo(self) -> None:
        self.assertEquals(1, 2)
        # Genesis block no guarda la tx en el chainstate.


if __name__ == '__main__':
    unittest.main()
