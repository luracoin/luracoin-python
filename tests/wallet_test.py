import sys, os, shutil
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from luracoin.wallet import address_to_pubkey
from luracoin.config import Config
import unittest

class BlocksTest(unittest.TestCase):
    
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_address_to_pubkey(self):
        pub_key = address_to_pubkey("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS")
        self.assertEqual(pub_key, "0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b")


if __name__ == '__main__':
    unittest.main()
