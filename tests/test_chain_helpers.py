from luracoin.chain import (
    Chain, blk_file_format, get_current_file_name,
    get_current_blk_file, close_databases,
)


def test_credit_account_new():
    chain = Chain()
    chain.credit_account("LTestAddr1234567890123456789012", 5000)
    account = chain.get_account("LTestAddr1234567890123456789012")
    assert account["balance"] == 5000
    assert account["nonce"] == 0


def test_credit_account_existing():
    chain = Chain()
    chain.set_account("LTestAddr1234567890123456789012", {"balance": 3000, "nonce": 2})
    chain.credit_account("LTestAddr1234567890123456789012", 2000)
    assert chain.get_account("LTestAddr1234567890123456789012")["balance"] == 5000


def test_debit_account():
    chain = Chain()
    chain.set_account("LTestAddr1234567890123456789012", {"balance": 10000, "nonce": 0})
    chain.debit_account("LTestAddr1234567890123456789012", 3000)
    assert chain.get_account("LTestAddr1234567890123456789012")["balance"] == 7000


def test_increment_nonce():
    chain = Chain()
    chain.set_account("LTestAddr1234567890123456789012", {"balance": 100, "nonce": 5})
    chain.increment_nonce("LTestAddr1234567890123456789012", 6)
    assert chain.get_account("LTestAddr1234567890123456789012")["nonce"] == 6
    assert chain.get_account("LTestAddr1234567890123456789012")["balance"] == 100


def test_blk_file_format():
    assert blk_file_format(0) == "000000"
    assert blk_file_format(1) == "000001"
    assert blk_file_format(999999) == "999999"


def test_get_current_file_name():
    assert get_current_file_name("000000") == "blk000000.dat"
    assert get_current_file_name("000132") == "blk000132.dat"


def test_get_current_blk_file():
    assert get_current_blk_file(0) == "blk000000.dat"
    assert get_current_blk_file(42) == "blk000042.dat"


def test_close_databases_no_error_when_empty():
    close_databases()  # Should not raise
