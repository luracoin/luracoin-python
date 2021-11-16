from tests.helpers import add_test_transactions
from luracoin.helpers import bits_to_target


def test_block_serialize(blockchain):
    bits = b'\x1d\x00\xff\xff'

    print(bits_to_target(bits))

    print("=======")

    test1 = "0000000010000006770c3806960539ca83a24facbd99ea212f37f2a0e6a5629a"
    assert int(test1, 16) <= int(bits_to_target(bits), 16)

    assert False
