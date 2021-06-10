import bsddb3
import os
import pickle


def create_bdb_object(filename):
    bdb = bsddb3.db.DB()
    bdb.set_flags(bsddb3.db.DB_DUP | bsddb3.db.DB_DUPSORT)
    open_flags = bsddb3.db.DB_CREATE | bsddb3.db.DB_EXCL
    if os.path.exists(filename):
        os.remove(filename)
    bdb.open(filename, dbtype=bsddb3.db.DB_BTREE, flags=open_flags)
    return bdb


def write_to_the_file(filename, data):
    bdb_filename = f'{filename}.new'
    bdb = create_bdb_object(bdb_filename)

    for url, record in data.items():
        bdb.put(url.encode(), pickle.dumps(record, protocol=2))

    bdb.close()
    os.rename(bdb_filename, filename)


def read_bdb(bdb_filename):
    bdb = bsddb3.db.DB()
    bdb.set_flags(bsddb3.db.DB_DUP | bsddb3.db.DB_DUPSORT)
    bdb.open(bdb_filename)
    bdb_cursor = bdb.cursor()

    record = bdb_cursor.first()
    counter = 1
    while record:
        print('Record num: %s, key: %s, value: %s' % (counter, record[0], pickle.loads(record[1])))
        record = bdb_cursor.next()
        counter += 1

    bdb_cursor.close()
    bdb.close()


def read_key_bdb(bdb_filename, key):
    bdb = bsddb3.db.DB()
    bdb.set_flags(bsddb3.db.DB_DUP | bsddb3.db.DB_DUPSORT)
    bdb.open(bdb_filename)
    result = bdb.get(key)
    bdb.close()

    if result:
        return pickle.loads(result)
    return result


def main():
    bdb_filename = '/Users/marcosaguayo/dev/luracoin-python/chain/bsddb.bdb'
    data = {'www.example1.com': 'lorem ipsum 1',
            'www.example2.com': 'lorem ipsum 2',
            'www.example3.com': 'lorem ipsum 3',
            'www.example4.com': 'lorem ipsum 4',
            'www.example5.com': 'lorem ipsum 5',
            'www.example6.com': 'lorem ipsum 6',
            'www.example7.com': 'lorem ipsum 7',
            'www.example8.com': 'lorem ipsum 8',
            'www.example9.com': 'lorem ipsum 9'}
    write_to_the_file(bdb_filename, data)

    read_bdb(bdb_filename)

    print("====")

    print("Start")
    
    result = read_key_bdb(bdb_filename, b'www.example1.com')

    print(result)

    print("End")


