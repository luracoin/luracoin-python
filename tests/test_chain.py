import pytest

from luracoin.chain import get_current_file_number, get_current_file_name


def test_get_current_file_number(blockchain):
    assert get_current_file_number() == "000000"


def test_get_current_file_name():
    assert get_current_file_name("000000") == "blk000000.dat"
    assert get_current_file_name("000001") == "blk000001.dat"
    assert get_current_file_name("021056") == "blk021056.dat"
