import os
import binascii


class Config:
    BASE_DIR = (
        os.path.normpath(os.getcwd() + os.sep + os.pardir) + "/luracoin-python"
    )

    WALLET_PATH = BASE_DIR + "/bin/wallet.dat"
    COINBASE_UNLOCK_SIGNATURE = binascii.unhexlify("0" * 256)

    # This will be appended at the end of Block and transaction transmission to
    # prevent other networks of currencies to capture them. Usually blockchains
    # have their own magic bytes.
    MAGIC_BYTES = b"\xbaw\xd8\x9f"

    MAX_TX_PER_BLOCK = 65535

    TRANSACTION_LENGTH = 179

    PORT = 9999

    # Data dir
    DATA_DIR = BASE_DIR + "/bin/data/"
    BLOCKS_DIR = DATA_DIR + "blocks/"

    # Max file size of each blkXXXX.dat in Bytes (128MiB)
    MAX_FILE_SIZE = 134_217_728

    # The infamous max block size.
    MAX_BLOCK_SERIALIZED_SIZE = 8_000_000  # bytes = 8MB

    # Number of blocks for a transaction to become balance
    TRANSACTION_MATURITY = 1

    # Accept blocks timestamped as being from the future, up to this amount.
    MAX_FUTURE_BLOCK_TIME = 500

    # The number of Lurashis per coin.
    LURASHIS_PER_COIN = int(100e6)

    COINS_TO_FORGE = 100_000 * LURASHIS_PER_COIN
    BLOCK_REWARD = 50 * LURASHIS_PER_COIN

    # REDIS
    #
    # Redis configuration and credentials
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 1
    REDIS_DB_TESTS = 9
