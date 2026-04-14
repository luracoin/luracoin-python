from luracoin.helpers import calculate_new_bits, bits_to_target


def test_calculate_new_bits_caps_at_max_target():
    """When difficulty decreases beyond max target, it should be capped."""
    # Use very low difficulty (high target) and make blocks very slow
    # to push target past the maximum
    high_target_bits = b"\x1f\xff\xff\xff"  # near-max target
    expected_time = 86400
    actual_time = expected_time * 4  # 4x slower => target goes up 4x

    new_bits = calculate_new_bits(high_target_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    max_target = int(bits_to_target(b"\x1f\xff\xff\xff"), 16)

    # New target should not exceed max target
    assert new_target <= max_target


def test_calculate_new_bits_small_exponent():
    """When target is very small, exponent < 3 should be handled."""
    # Very low target = very high difficulty
    # Use bits that produce a tiny target
    tiny_bits = b"\x03\x00\x00\x01"  # exponent=3, coefficient=000001 => target = 1
    expected_time = 86400
    actual_time = 86400  # same time => target stays same

    new_bits = calculate_new_bits(tiny_bits, actual_time, expected_time)
    assert len(new_bits) == 4
    assert isinstance(new_bits, bytes)
