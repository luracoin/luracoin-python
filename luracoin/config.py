import os
import binascii


class Config:
    BASE_DIR = (
        os.path.normpath(os.getcwd() + os.sep + os.pardir) + "/luracoin-python"
    )

    WALLET_PATH = BASE_DIR + "/bin/wallet.dat"
    COINBASE_UNLOCK_SIGNATURE = binascii.unhexlify("0" * 256)
    STAKING_ADDRESS = "0" * 34

    # This will be appended at the end of Block and transaction transmission to
    # prevent other networks of currencies to capture them. Usually blockchains
    # have their own magic bytes.
    MAGIC_BYTES = b"\xbaw\xd8\x9f"

    STARTING_DIFFICULTY = b"\x1d\xff\xff\xff"

    MAX_TX_PER_BLOCK = 65535

    TRANSACTION_LENGTH = 179

    PORT = 9999

    # Data dir
    DATA_DIR = BASE_DIR + "/data/"
    DATA_TEST_DIR = BASE_DIR + "/tests/data/"
    BLOCKS_DIR = DATA_DIR + "blocks/"
    BLOCKS_TEST_DIR = DATA_TEST_DIR + "blocks/"

    DATABASE_ACCOUNTS = "accounts.db"
    DATABASE_CHAINSTATE = "chainstate.db"
    DATABASE_BLOCKS = "blocks.db"

    # Max file size of each blkXXXX.dat in Bytes (128MiB)
    MAX_FILE_SIZE = 134_217_728

    # The infamous max block size.
    MAX_BLOCK_SIZE = {
        0: 10_000,
        28_800: 50_000,
        57_600: 75_000,
        86_400: 200_000,
        172_800: 1_000_000,
        259_200: 2_000_000,
        345_600: 3_000_000,
        432_000: 8_000_000,
    }
    MAX_BLOCK_SERIALIZED_SIZE = 8_000_000  # bytes = 8MB

    # Number of blocks for a transaction to become balance
    TRANSACTION_MATURITY = 1

    # Accept blocks timestamped as being from the future, up to this amount.
    MAX_FUTURE_BLOCK_TIME = 500

    # The number of Lurashis per coin.
    LURASHIS_PER_COIN = int(100e6)

    COINS_TO_FORGE = 100_000 * LURASHIS_PER_COIN
    BLOCK_REWARD = 50 * LURASHIS_PER_COIN
    HALVING_BLOCKS = 172_800 * 1.5  # Every 1.5 years aprox

    # REDIS
    #
    # Redis configuration and credentials
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 1
    REDIS_DB_TESTS = 9
