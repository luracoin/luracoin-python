from luracoin.blocks import next_blk_file, serialize_block
from luracoin.search import blk_to_list, find_block_in_file
from luracoin.serialize import deserialize_block
from luracoin.blockchain import TxOut, TxIn, Transaction, OutPoint, Block
from luracoin.transactions import build_message, build_p2pkh, build_script_sig
from luracoin.wallet import bytes_to_signing_key

from tests.blockchain_test import LuracoinTest
import unittest


class BlocksTest(LuracoinTest):

    maxDiff = None

    def test_blk_to_list(self):
        self.assertEqual(len(blk_to_list('000000', True)), 2)
        self.assertEqual(len(blk_to_list('000000')), 2)

    def test_next_blk_file(self):
        self.assertEqual(next_blk_file('000000'), '000001')
        self.assertEqual(next_blk_file('000009'), '000010')
        self.assertEqual(next_blk_file('000020'), '000021')
        self.assertEqual(next_blk_file('000099'), '000100')

    def test_find_block_in_file(self):
        block = find_block_in_file(blk_height=0, blk_file='000000')
        self.assertEqual(block.id, self.genesis_block.id)

    def test_serialize_block(self):
        signature = bytes_to_signing_key(self.private_key2).sign(
            build_message(
                OutPoint(self.tx2.id, 0),
                self.public_key2
            ).encode()
        )

        tx = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(to_spend=OutPoint(0, -1), unlock_sig='1', sequence=0)
            ],
            txouts=[
                TxOut(value=5000000000, to_address=build_p2pkh(self.address1))
            ]
        )

        tx1 = Transaction(
            version=1, locktime=0,
            txins=[
                TxIn(
                    to_spend=OutPoint(tx.id, 0), sequence=0,
                    unlock_sig=build_script_sig(
                        signature.hex(), self.public_key1
                    )
                )
            ],
            txouts=[
                TxOut(
                    value=1000000000,
                    to_address=build_p2pkh(self.address2)
                ),
                TxOut(
                    value=2000000000,
                    to_address=build_p2pkh(self.address3)
                ),
                TxOut(
                    value=2000000000,
                    to_address=build_p2pkh(self.address3)
                )
            ]
        )

        block1 = Block(
            version=1,
            prev_block_hash="56254692955540c5e15ccc5f374c507e785f8c87ddd89"
                            "b22279556153cf34061",
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
        self.assertEqual(
            block1_new.txns[0].txins[0].to_spend,
            block1.txns[0].txins[0].to_spend
        )
        self.assertEqual(
            block1_new.txns[0].txins[0].unlock_sig,
            block1.txns[0].txins[0].unlock_sig
        )
        self.assertEqual(
            block1_new.txns[0].txins[0].sequence,
            block1.txns[0].txins[0].sequence
        )
        self.assertEqual(
            block1_new.txns[0].txouts[0].value,
            block1.txns[0].txouts[0].value
        )
        self.assertEqual(
            block1_new.txns[0].txouts[0].to_address,
            block1.txns[0].txouts[0].to_address
        )
        self.assertEqual(block1_new.txns[0].id, block1.txns[0].id)

        self.assertEqual(block1_new.txns[1].version, block1.txns[1].version)
        self.assertEqual(block1_new.txns[1].locktime, block1.txns[1].locktime)
        self.assertEqual(
            block1_new.txns[1].txins[0].to_spend,
            block1.txns[1].txins[0].to_spend
        )
        self.assertEqual(
            block1_new.txns[1].txins[0].unlock_sig,
            block1.txns[1].txins[0].unlock_sig
        )
        self.assertEqual(
            block1_new.txns[1].txins[0].sequence,
            block1.txns[1].txins[0].sequence
        )
        self.assertEqual(
            block1_new.txns[1].txouts[0].value,
            block1.txns[1].txouts[0].value
        )
        self.assertEqual(
            block1_new.txns[1].txouts[0].to_address,
            block1.txns[1].txouts[0].to_address
        )
        self.assertEqual(block1_new.txns[1].id, block1.txns[1].id)

        self.assertEqual(block1_new.prev_block_hash, block1.prev_block_hash)


if __name__ == '__main__':
    unittest.main()
