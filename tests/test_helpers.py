from luracoin.helpers import little_endian, var_int


def test_var_int() -> None:
    assert var_int(252) == "fc"
    assert var_int(1276) == "fdfc04"
    assert var_int(10276) == "fd2428"
    assert var_int(100_000) == "fea0860100"
    assert var_int(1_000_000) == "fe40420f00"
    assert var_int(10_000_000) == "fe80969800"
    assert var_int(5_000_000_000) == "ff00f2052a01000000"


def test_little_endian() -> None:
    assert little_endian(num_bytes=5, data=15) == "0f00000000"
    assert little_endian(num_bytes=4, data=15) == "0f000000"
    assert little_endian(num_bytes=3, data=15) == "0f0000"
    assert little_endian(num_bytes=2, data=19) == "1300"
    assert little_endian(num_bytes=1, data=19) == "13"


def test_sha256d() -> None:
    # TODO: Test for sha256d
    pass


def test_var_int_to_bytes() -> None:
    # TODO: Test for var_int_to_bytes
    pass


def test_() -> None:
    pass