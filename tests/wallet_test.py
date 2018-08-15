import sys, os, shutil
import unittest
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from luracoin.wallet import address_to_pubkey, bytes_to_signing_key
from luracoin.config import Config


class BlocksTest(unittest.TestCase):

    def test_bytes_to_signing_key(self):
        sig_key = bytes_to_signing_key(
            b'\xb1\x80E\xceRo\xfeG[\x89\xe2\xc1+\xfd\xf9\xc4\x80w\x91\x836o~\xbe\x87\x82bb\xab@\xf9N')
        self.assertEqual(sig_key.to_string().hex(), 'b18045ce526ffe475b89e2c12bfdf9c480779183366f7ebe87826262ab40f94e')

    def test_address_to_pubkey(self):
        pub_key = address_to_pubkey("1DNFUMhT4cm4qbZUrbAApN3yKJNUpRjrTS")
        self.assertEqual(pub_key, "0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b")


if __name__ == '__main__':
    unittest.main()
