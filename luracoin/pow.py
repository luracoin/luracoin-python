import hashlib


def proof_of_work(last_proof):
    """
    Simple Proof of Work Algorithm:
    - Find a number p' such that hash(pp') contains leading 4 zeroes,
      where p is the previous p'
    - p is the previous proof, and p' is the new proof

    :param last_proof: Proof of work of the previous block
    :return: Proof of Work
    """

    proof = 0
    stop_loop = False
    while stop_loop is False:
        proof += 1
        stop_loop = valid_proof(last_proof, proof)

    return proof


def valid_proof(last_proof, proof):
    """
    Validates the Proof

    :param last_proof: Previous Proof
    :param proof: Current Proof
    :return: True if correct, False if not.
    """
    str_proof = str(last_proof) + str(proof)
    guess = str_proof.encode()
    guess_hash = hashlib.sha256(guess).hexdigest()
    return guess_hash[:1] == "0"


def validate_pow(block):
    return True


def mining_reward():
    return 50
