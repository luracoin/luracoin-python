import hashlib
import os
from typing import Iterable, Union

import plyvel

from .config import Config


def sha256d(s: Union[str, bytes]) -> str:
    """A double SHA-256 hash."""
    if not isinstance(s, bytes):
        s = s.encode()

    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


def _chunks(l, n) -> Iterable[Iterable]:
    return (l[i : i + n] for i in range(0, len(l), n))


def var_int(num: int) -> str:
    if num <= 252:
        num = num.to_bytes(1, byteorder="little", signed=False).hex()
    elif num <= 65535:
        num = "fd" + num.to_bytes(2, byteorder="little", signed=False).hex()
    elif num <= 4294967295:
        num = "fe" + num.to_bytes(4, byteorder="little", signed=False).hex()
    else:
        num = "ff" + num.to_bytes(8, byteorder="little", signed=False).hex()

    return num


def deserialize_var_int():
    return 0


def get_blk_file_size(file_name: str) -> int:
    path = Config.BLOCKS_DIR + file_name
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def get_current_height():
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    heigth = db.get(b"b")
    db.close()

    return int(heigth.decode())
