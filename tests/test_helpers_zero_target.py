from luracoin.helpers import calculate_new_bits


def test_calculate_new_bits_zero_target():
    """calculate_new_bits with zero coefficient should return zero bits."""
    # Bits with zero coefficient => target = 0
    zero_bits = b"\x04\x00\x00\x00"
    result = calculate_new_bits(zero_bits, 86400, 86400)
    assert result == b"\x00\x00\x00\x00"
