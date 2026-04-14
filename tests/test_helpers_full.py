from luracoin.helpers import little_endian_to_int, calculate_new_bits


def test_little_endian_to_int():
    assert little_endian_to_int("01000000") == 1
    assert little_endian_to_int("ff000000") == 255
    assert little_endian_to_int("00000001") == 16777216
    assert little_endian_to_int("e8030000") == 1000


def test_little_endian_to_int_zero():
    assert little_endian_to_int("00000000") == 0


def test_calculate_new_bits_returns_bytes():
    result = calculate_new_bits(b"\x1d\x00\xff\xff", 86400, 86400)
    assert isinstance(result, bytes)
    assert len(result) == 4
