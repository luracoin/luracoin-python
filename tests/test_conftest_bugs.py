import re
import inspect
from tests.conftest import init_blockchain


def test_genesis_bits_uses_hex_escape_not_octal():
    """
    Bug 1.2: conftest init_blockchain() uses bits=b"\\1f\\x00\\xff\\xff".
    \\1f is octal \\1 (0x01) + literal 'f' (0x66) = 2 bytes, making 5 total.
    Should be b"\\x1f\\x00\\xff\\xff" (4 bytes).

    We verify the source code doesn't contain the malformed escape sequence.
    """
    source = inspect.getsource(init_blockchain)
    # The raw string b"\1f" in source appears as: \\1f (not \\x1f)
    # Find the bits= assignment line
    assert 'bits=b"\\1f' not in source, (
        'conftest uses b"\\1f..." (octal \\1 + literal f = 5 bytes). '
        'Should be b"\\x1f..." (hex 0x1f = 4 bytes).'
    )
