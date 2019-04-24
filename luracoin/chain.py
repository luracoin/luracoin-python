import plyvel
from luracoin.config import Config
from luracoin.helpers import little_endian, get_blk_file_size


def get_current_file_number() -> str:
    # Get the current file
    db = plyvel.DB(Config.BLOCKS_DIR + "index", create_if_missing=True)
    file_number = db.get(b"l")
    db.close()

    # If there is not a current file we'll start by '000000'
    if file_number is None or file_number == "" or file_number == b"":
        file_number = "000000"
    else:
        file_number = file_number.decode("utf-8")

    file_name = get_current_file_name(file_number)
    if get_blk_file_size(file_name) >= Config.MAX_FILE_SIZE:
        file_number = next_blk_file(file_number)

    try:
        return file_number.decode("utf-8")
    except AttributeError:
        return str(file_number)


def get_current_file_name(file_number: str) -> str:
    return f"blk{file_number}.dat"


def get_current_blk_file() -> str:
    number = get_current_file_number()
    return get_current_file_name(number)


def serialise_block_to_save(serialised_block: str) -> str:
    """
    Serialise the block for saving it on the blkXXXXX.dat files.
    We have to add the length of the serialised block between the Magic bytes
    and the content.
    """

    # Length of the serialised block without the Magic bytes
    serialised_block_length_without_magic_bytes = int(
        len(serialised_block) - 8
    )

    block_length = little_endian(
        num_bytes=4, data=serialised_block_length_without_magic_bytes
    )

    # MAGIC + LENGTH + BLOCK
    serialised_block = (
        serialised_block[:8] + block_length + serialised_block[8:]
    )

    return serialised_block


def next_blk_file(current_blk_file: str) -> str:
    """
    Increases by one the blk file name, for example:
    blk000132.dat => blk000133.dat

    :param current_blk_file: <String> Actual file (eg. 000001)
    :return: <String> Next file (eg. 000002)
    """
    return str(int(current_blk_file) + 1).zfill(6)
