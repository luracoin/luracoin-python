import os
import pickledb

CHAIN_FILENAME = 'chainstate.bdb'


def open_chain_database():
    db = pickledb.load(CHAIN_FILENAME, False)
    return db


def set_value(key, value):
    db = open_chain_database()
    db.set(key, value)


def get_value(key):
    db = open_chain_database()
    return db.get(key)
