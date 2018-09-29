import unittest
import os
import shutil
from luracoin.blocks import serialize_block, add_block_to_chain
from luracoin.blockchain import TxOut, TxIn, Transaction, OutPoint, Block
from luracoin.transactions import build_message, build_p2pkh, build_script_sig
from luracoin.config import Config
from luracoin.wallet import bytes_to_signing_key


class LuracoinTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Config.DATA_DIR = Config.BASE_DIR + '/tests/data/'
        Config.BLOCKS_DIR = Config.DATA_DIR + 'blocks/'

        folder = Config.BLOCKS_DIR
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)

        # User 1
        cls.public_key1 = "79b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f" \
            "42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f" \
            "41f0b3d39498cb65b3ee"
        cls.address1 = "1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS"
        cls.private_key1 = (b'\xb1\x80E\xceRo\xfeG[\x89\xe2\xc1+\xfd\xf9\xc4'
                            b'\x80w\x91\x836o~\xbe\x87\x82bb\xab@\xf9N')

        # User 2
        cls.public_key2 = "7b11afeeb5e0a40d14541774c5cf8db6c22dfc98594ca88" \
            "0270fe6fc12f29da564d90f3cc829e18d1879388dacc931fbbc43fa1c4479" \
            "f4798cf1c82da103e398"
        cls.address2 = "12ZoTwtd7xCKqCzazobCHZsfNLdz7nDPsr"
        cls.private_key2 = (b'\xea\xe1\xb8-\xdc\x9fd\xc2\x07/]\x1a\t\xac|'
                            b'\x871\x9c\xa8R.\xbe\xdb\xfe\xce\x953\xbb{O'
                            b'\xda"')

        # User 3
        cls.public_key3 = "cd1aee50b5e08b2b9512ed72c6aefbb35f762512b05a971" \
            "6a697ac631afed91f82adffae311dcb1a7e54f688c099bd489fd1e3e3aed0" \
            "11009cbf6bb4c2816ddf"
        cls.address3 = "1CtwoH41qLqMTMt6YSbVcqJieu3T9ZFCz3"
        cls.private_key3 = (b'\xc6H\t\xa6y\x8d\xa9\x1dj\xf6\xa0\xbb\xd4:'
                            b'\xbbi\xe5.GMH~\x00\xc5\x02\x97k\x01)[B\xf5')

        # User 4
        cls.public_key4 = "f4b076bfcdb1f782018d2e3afa195ae1c92f18b3f97ba0c" \
            "a1a9923bd48291817f8ba9a2dbe2fd347b5a75998221022a548c9bfb32670" \
            "4c021870ccce90c6e1df"
        cls.address4 = "1HnEUP63BuFBJPcL3ovJc3rq78Tq4vovP6"
        cls.private_key4 = (b'\x13\x18\xff\xfd]\x18-.\xa7\xb6\x0c\xeaX\xf6&'
                            b"\x92\x0fC\x16B|\x95`\x8e\x92/\\nlN'\xe8")

        # ===================================================
        # ================== GENESIS BLOCK ==================

        cls.tx0 = Transaction(
            version=1,
            txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig='0', sequence=0)],
            txouts=[
                TxOut(value=5000000000, to_address=build_p2pkh(cls.address1))
            ],
            locktime=0
        )

        cls.genesis_block = Block(
            version=1,
            prev_block_hash=Config.COINBASE_TX_ID,
            timestamp=1501821412,
            bits=24,
            nonce=11111111,
            txns=[cls.tx0]
        )

        add_block_to_chain(serialize_block(cls.genesis_block))

        # ===================================================
        # ====================  BLOCK 1 =====================

        signature = bytes_to_signing_key(cls.private_key1).sign(
            build_message(
                OutPoint(cls.tx0.id, 0),
                cls.public_key1
            ).encode()
        )

        cls.tx1 = Transaction(
            version=1,
            txins=[TxIn(to_spend=OutPoint(0, -1), unlock_sig='1', sequence=0)],
            txouts=[
                TxOut(value=5000000000, to_address=build_p2pkh(cls.address1))
            ],
            locktime=0
        )

        cls.tx2 = Transaction(
            version=1,
            txins=[
                TxIn(
                    to_spend=OutPoint(cls.tx0.id, 0), sequence=0,
                    unlock_sig=build_script_sig(
                            signature.hex(),
                            cls.public_key1
                        )
                    )
            ],
            txouts=[
                TxOut(value=1000000000, to_address=build_p2pkh(cls.address2)),
                TxOut(value=2000000000, to_address=build_p2pkh(cls.address3)),
                TxOut(value=2000000000, to_address=build_p2pkh(cls.address4))
            ],
            locktime=0
        )

        cls.block1 = Block(
            version=1,
            prev_block_hash=cls.genesis_block.id,
            timestamp=1501821412,
            bits=24,
            nonce=10126761,
            txns=[cls.tx1, cls.tx2]
        )

        add_block_to_chain(serialize_block(cls.block1))

        # ===================================================
        # ====================  BLOCK 2 =====================

        # ===================================================
        # ====================  BLOCK 3 =====================

        # ===================================================
        # ====================  BLOCK 4 =====================

        # ===================================================
        # ====================  BLOCK 5 =====================

        # ===================================================
        # ====================  BLOCK 6 =====================

    @classmethod
    def tearDownClass(cls):
        folder = Config.DATA_DIR
        if os.path.exists(folder):
            shutil.rmtree(folder)
