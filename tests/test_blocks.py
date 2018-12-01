from luracoin.blocks import Block


def test_block_id(block1):  # type: ignore
    assert block1.id == (
        "410fc1eea0e6e7fd0b117e09c6612415fa3c1370c2f595427e3757e3daf02640"
    )


def test_block_serialize(block1):  # type: ignore
    assert block1.serialize() == (
        "ba77d89f010000000000000000000000000000000000000000000000000000000000"
        "000000000000410fc1eea0e6e7fd0b117e09c6612415fa3c1370c2f595427e3757e3"
        "daf0264018000000e4f98359a9859a00000001010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff0100000000003005ed0b"
        "2000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac002f6"
        "859000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac006"
        "5cd1d000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac"
    )


def test_block_deserialize(block1):  # type: ignore
    block = Block()

    block.deserialize(
        "ba77d89f010000000000000000000000000000000000000000000000000000000000"
        "000000000000410fc1eea0e6e7fd0b117e09c6612415fa3c1370c2f595427e3757e3"
        "daf0264018000000e4f98359a9859a00000001010001000000000000000000000000"
        "0000000000000000000000000000000000000000ffffffff0100000000003005ed0b"
        "2000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac002f6"
        "859000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac006"
        "5cd1d000000003476a9150087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b88ac"
    )

    assert block.version == block1.version
    assert block.timestamp == block1.timestamp
    assert block.bits == block1.bits
    assert block.nonce == block1.nonce
    assert block.prev_block_hash == block1.prev_block_hash
    # TODO: Transactions
