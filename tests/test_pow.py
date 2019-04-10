from luracoin.pow import proof_of_work
from tests.constants import BLOCK3_VALID_NONCE


def test_proof_of_work(block3):  # type: ignore
    proof = proof_of_work(block3)
    assert block3.is_valid_proof
    assert proof == BLOCK3_VALID_NONCE
