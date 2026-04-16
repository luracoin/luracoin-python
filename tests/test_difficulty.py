from luracoin.helpers import calculate_new_bits, bits_to_target


def test_difficulty_increases_when_blocks_are_fast():
    """If blocks came in 2x faster than expected, difficulty should increase (lower target)."""
    prev_bits = b"\x1d\x00\xff\xff"
    expected_time = 86400  # 1 day
    actual_time = 43200    # half a day (blocks too fast)

    new_bits = calculate_new_bits(prev_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    old_target = int(bits_to_target(prev_bits), 16)

    assert new_target < old_target


def test_difficulty_decreases_when_blocks_are_slow():
    """If blocks came in 2x slower than expected, difficulty should decrease (higher target)."""
    prev_bits = b"\x1d\x00\xff\xff"
    expected_time = 86400
    actual_time = 172800   # double the expected time

    new_bits = calculate_new_bits(prev_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    old_target = int(bits_to_target(prev_bits), 16)

    assert new_target > old_target


def test_difficulty_unchanged_when_on_schedule():
    """If blocks came exactly on time, target should stay roughly the same."""
    prev_bits = b"\x1d\x00\xff\xff"
    expected_time = 86400
    actual_time = 86400

    new_bits = calculate_new_bits(prev_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    old_target = int(bits_to_target(prev_bits), 16)

    # Allow small rounding differences
    ratio = new_target / old_target
    assert 0.99 <= ratio <= 1.01


def test_difficulty_clamped_at_4x_increase():
    """Even if blocks are 100x faster, clamp adjustment to 4x."""
    prev_bits = b"\x1d\x00\xff\xff"
    expected_time = 86400
    actual_time = 100  # absurdly fast

    new_bits = calculate_new_bits(prev_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    old_target = int(bits_to_target(prev_bits), 16)

    # Should be clamped to 1/4 of old target
    ratio = new_target / old_target
    assert 0.24 <= ratio <= 0.26


def test_difficulty_clamped_at_4x_decrease():
    """Even if blocks are 100x slower, clamp adjustment to 4x."""
    prev_bits = b"\x1d\x00\xff\xff"
    expected_time = 86400
    actual_time = 86400 * 100  # absurdly slow

    new_bits = calculate_new_bits(prev_bits, actual_time, expected_time)
    new_target = int(bits_to_target(new_bits), 16)
    old_target = int(bits_to_target(prev_bits), 16)

    # Target should increase but be clamped (not go higher than ~4x)
    assert new_target > old_target
    ratio = new_target / old_target
    assert ratio <= 4.1


def test_new_bits_returns_4_bytes():
    new_bits = calculate_new_bits(b"\x1d\x00\xff\xff", 86400, 86400)
    assert len(new_bits) == 4
