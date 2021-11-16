import time
import json
import hashlib
from typing import Union


tx = {
	"h": "46ca88045e07d6f03ba897a2be046ee6d3ebd8fd43f8a1a3f0812da54cfca691",
	"v": 1,
	"l": 664057696, # lock_time
	"i": [{
		"t": "46ca88045e07d6f03ba897a2be046ee6d3ebd8fd43f8a1a3f0812da54cfca691",
		"idx": "9999",
		"u": "8076dcafb25fe499ac8614e811a30e50d995fc80bd38ad9d2d6c73a3dbb6f848792637cb9566b43671b4374ef055acfcfda5268461f4e95449d4ad9858891fadff805c440bc46d316dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1eab11c4af165e4ce3eb0652f8d937620804fe15201c00a7466f56237810988db1",
		"s": 0,
	}],
	"o": [{
		"v": 50000,
		"a": "1EepjXgvWUoRyNvuLSAxjiqZ1QqKGDANLW"
	}, {
		"v": 50000,
		"a": "1EepjXgvWUoRyNvuLSAxjiqZ1QqKGDANLW"
	}]
}

def sha256d(s: Union[str, bytes]) -> str:
    """A double SHA-256 hash."""
    if not isinstance(s, bytes):
        s = s.encode()

    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()

def hash_transaction(transaction):
    content = transaction["h"] + str(transaction["v"]) + str(transaction["l"])
    for tx_in in transaction["i"]:
        content += tx_in["t"]

    for tx_out in transaction["o"]:
        content += str(tx_out["v"]) + str(tx_out["a"])
    
    return sha256d(content)


# Bitcoin: 75.751.362
start = time.time()
txIds = ""
for i in range(75751360):
    tx["h"] = tx["h"][:63] + str(i)
    actual = hash_transaction(tx) 
    txIds += actual

utxo_hash = sha256d(txIds)
end = time.time()
print(end - start)
print(utxo_hash)
