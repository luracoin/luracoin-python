from luracoin.chain import max_block_size


def test_max_block_size_at_height_0():
    assert max_block_size(0) == 10_000


def test_max_block_size_before_first_threshold():
    assert max_block_size(28_799) == 10_000


def test_max_block_size_at_first_threshold():
    assert max_block_size(28_800) == 50_000


def test_max_block_size_at_second_threshold():
    assert max_block_size(57_600) == 75_000


def test_max_block_size_at_third_threshold():
    assert max_block_size(86_400) == 200_000


def test_max_block_size_at_1mb():
    assert max_block_size(172_800) == 1_000_000


def test_max_block_size_at_8mb():
    assert max_block_size(432_000) == 8_000_000


def test_max_block_size_far_future():
    assert max_block_size(999_999) == 8_000_000
