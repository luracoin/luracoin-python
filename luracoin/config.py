import os


class Config:
    BASE_DIR = (
        os.path.normpath(os.getcwd() + os.sep + os.pardir) + "/luracoin-python"
    )

    WALLET_PATH = BASE_DIR + "/bin/wallet.dat"

    MAGIC_BYTES = "ba77d89f"

    MAX_TX_PER_BLOCK = 65535

    PORT = 9999

    # Data dir
    DATA_DIR = BASE_DIR + "/bin/data/"
    BLOCKS_DIR = DATA_DIR + "blocks/"

    # Max file size of each blkXXXX.dat in Bytes (128MiB)
    MAX_FILE_SIZE = 134_217_728

    # The infamous max block size.
    MAX_BLOCK_SERIALIZED_SIZE = 8_000_000  # bytes = 1MB

    # Coinbase transaction outputs can be spent after this many blocks have
    # elapsed since being mined.
    #
    # This is "100" in bitcoin core.
    COINBASE_MATURITY = 100

    COINBASE_TX_ID = (
        "0000000000000000000000000000000000000000000000000000000000000000"
    )

    COINBASE_TX_INDEX = "ffffffff"

    # Accept blocks timestamped as being from the future, up to this amount.
    MAX_FUTURE_BLOCK_TIME = 60 * 60 * 15

    # The number of Belushis per coin. #realname COIN
    BELUSHIS_PER_COIN = int(100e6)

    TOTAL_COINS = 21_000_000_000

    # The maximum number of Belushis that will ever be found.
    MAX_MONEY = BELUSHIS_PER_COIN * TOTAL_COINS

    # The duration we want to pass between blocks being found, in seconds.
    # This is lower than Bitcoin's configuation (10 * 60).
    #
    # #realname PowTargetSpacing
    TIME_BETWEEN_BLOCKS_TARGET = 5 * 60

    # The number of seconds we want a difficulty period to last.
    #
    # Note that this differs considerably from the behavior in Bitcoin, which
    # is configured to target difficulty periods of (10 * 2016) minutes.
    #
    # #realname PowTargetTimespan
    DIFFICULTY_PERIOD_TARGET = 60 * 60 * 10

    # After this number of blocks are found, adjust difficulty.
    #
    # #realname DifficultyAdjustmentInterval
    DIFFICULTY_PERIOD_IN_BLOCKS = (
        DIFFICULTY_PERIOD_TARGET / TIME_BETWEEN_BLOCKS_TARGET
    )

    # The number of right-shifts applied to 2 ** 256 in order to create the
    # initial difficulty target necessary for mining a block.
    INITIAL_DIFFICULTY_BITS = 24

    # The number of blocks after which the mining subsidy will halve.
    #
    # #realname SubsidyHalvingInterval
    HALVE_SUBSIDY_AFTER_BLOCKS_NUM = 210_000
