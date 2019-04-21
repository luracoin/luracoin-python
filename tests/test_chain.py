from luracoin.chain import get_current_file_number, get_current_file_name


def test_get_current_file_number(blockchain) -> None:  # type: ignore
    assert get_current_file_number() == "000000"


def test_get_current_file_name() -> None:
    assert get_current_file_name("000000") == "blk000000.dat"
    assert get_current_file_name("000001") == "blk000001.dat"
    assert get_current_file_name("021056") == "blk021056.dat"
