import plyvel
from luracoin.config import Config

def get_current_file_number() -> str:
    # Get the current file
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    file_number = db.get(b"l")

    # If there is not a current file we'll start by '000000'
    if (
        file_number is None
        or file_number == ""
        or file_number == b""
    ):
        file_number = "000000"
    else:
        file_number.decode("utf-8")

    db.close()

    return file_number


def get_current_file_name(file_number: str) -> str:
    return f"blk{file_number}.dat"
