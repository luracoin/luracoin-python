from .config import Config
from .serialize import deserialize_block


def blk_to_list(blk_number: str, raw: bool=False) -> list:
    """
    Get the contents of a blk file and create a list with all blocks within.

    :param blk_number: <String> Filename (eg. 026113)
    :return: <List>
    """
    try:
        f = open(Config.BLOCKS_DIR + "blk" + blk_number + ".dat", 'r')
        contents = f.read()
        f.close()
        block_list = contents.split(Config.MAGIC_BYTES)
        block_list = [l for l in block_list if l]
        if not raw:
            block_list = [deserialize_block(bl) for bl in block_list]
        return block_list
    except FileNotFoundError:
        return []


def find_block_in_file(blk_height: int, blk_file: str):
    """
    Find a block inside a blk file

    :param blk_height:
    :param blk_file:
    :return:
    """
    blk_list = blk_to_list(blk_file)

    for bl in blk_list:
        if int(bl.txns[0].txins[0].unlock_sig) == int(blk_height):
            return bl

    return False