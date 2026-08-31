from types import SimpleNamespace

from luracoin.chain import Chain
from tests.constants import WALLET_1, WALLET_2


def _transaction(identifier, sender, receiver):
    return SimpleNamespace(
        id=f"{identifier:064x}",
        from_address=sender,
        to_address=receiver,
    )


def test_address_history_index_is_newest_first_and_cursor_paginated():
    chain = Chain()
    first = _transaction(1, WALLET_1["address"], WALLET_2["address"])
    self_send = _transaction(2, WALLET_1["address"], WALLET_1["address"])
    latest = _transaction(3, WALLET_2["address"], WALLET_1["address"])

    for height, transaction in enumerate((first, self_send, latest), start=1):
        block_id = f"{height + 100:064x}"
        chain.commit_block_metadata(
            height=height,
            file_number=0,
            block_id=block_id,
            transactions=[transaction],
        )
        assert chain.get_block_height(block_id) == height

    page, cursor = chain.get_address_transaction_refs(
        WALLET_1["address"], limit=2
    )
    assert [(item["height"], item["transaction_id"]) for item in page] == [
        (3, latest.id),
        (2, self_send.id),
    ]
    assert cursor == page[-1]["cursor"]

    remaining, next_cursor = chain.get_address_transaction_refs(
        WALLET_1["address"], limit=2, cursor=cursor
    )
    assert [
        (item["height"], item["transaction_id"]) for item in remaining
    ] == [(1, first.id)]
    assert next_cursor is None

    exact_page, exact_cursor = chain.get_address_transaction_refs(
        WALLET_2["address"], limit=2
    )
    assert len(exact_page) == 2
    assert exact_cursor is None

    assert chain.get_block_height("not-a-block-id") is None
    assert chain.get_block_height("f" * 64) is None
