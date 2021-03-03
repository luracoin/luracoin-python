from luracoin.blocks import Block
from luracoin.config import Config
from tests.transactions.constants import (
    COINBASE1,
    COINBASE2,
    COINBASE3,
    COINBASE4,
    COINBASE5,
    COINBASE6,
    TRANSACTION1,
    TRANSACTION2,
    TRANSACTION3,
    TRANSACTION4,
    TRANSACTION5,
    TRANSACTION6,
)

# --------------- BLOCK 1 ---------------
BLOCK1_VALID_NONCE = 5_838_058
BLOCK1_ID = "0000043cc8fcd5dd8442ce9b183f0f90edaa8b99a6a00f612262bbb60aad9126"
BLOCK1 = Block(
    version=1,
    prev_block_hash=Config.COINBASE_TX_ID,
    timestamp=1_501_821_412,
    bits="1e0fffff",
    nonce=BLOCK1_VALID_NONCE,  # one less than the real nonce
)
BLOCK1.txns = [COINBASE1]
BLOCK1_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa9timestamp\xceY\x83\xf9\xe4\xa4bits\xa81e0fffff\xa5nonce\xce\x00\x15K\x7f\xa4txns\x91\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa11\xa8sequence\x00\xa6txouts\x93\x82\xa5value\xce\xb2\xd0^\x00\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b\x82\xa5value\xceYh/\x00\xaato_address\xd9*00112c3926e5e63ef39aae10a1b5cf0f57f54d6752\x82\xa5value\xce\x1d\xcde\x00\xaato_address\xd9*00827c5733e1401c1daaaaa3739ed5ad2acfd9ce4a\xa8locktime\x00"

# --------------- BLOCK 2 ---------------
BLOCK2_VALID_NONCE = 2_928_808
BLOCK2_ID = "00000aea19cc0a53aae04358726c57b25ae911cc7c7b1f43524a5440e8884d91"
BLOCK2 = Block(
    version=1,
    prev_block_hash=BLOCK1_ID,
    timestamp=1_501_823_000,
    bits="1e0fffff",
    nonce=BLOCK2_VALID_NONCE - 1,  # one less than the real nonce
)
BLOCK2.txns = [COINBASE2]
BLOCK2_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@00000b247dbfaa645213f7f7c0cc64429457b23472e83cc77de42c217512fa5d\xa9timestamp\xceY\x84\x00\x18\xa4bits\xa81e0fffff\xa5nonce\xce\x00!\xcab\xa4txns\x91\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa12\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcf\x00\x00\x00\x01*\x05\xf2\x00\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b\xa8locktime\x00"

# --------------- BLOCK 3 ---------------
BLOCK3_VALID_NONCE = 1_273_735
BLOCK3_ID = "00000cceef98253d87d559c3a4ea0e7b8ad83c38e2770fadb9ccd51d537dd7b2"
BLOCK3 = Block(
    version=1,
    prev_block_hash=BLOCK2_ID,
    timestamp=1_501_823_500,
    bits="1e0fffff",
    nonce=BLOCK3_VALID_NONCE - 1,  # one less than the real nonce
)
BLOCK3.txns = [COINBASE3]
BLOCK3_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@00000f34d7ab5f098ff6c0b9f23339d53937178121d0985f18ec446e549379eb\xa9timestamp\xceY\x84\x02\x0c\xa4bits\xa81e0fffff\xa5nonce\xce\x00\n\xedB\xa4txns\x91\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa13\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcf\x00\x00\x00\x01*\x05\xf2\x00\xaato_address\xd9*00112c3926e5e63ef39aae10a1b5cf0f57f54d6752\xa8locktime\x00"

# --------------- BLOCK 4 ---------------
BLOCK4_VALID_NONCE = 1_895_745
BLOCK4_ID = "000001dc7aad273c95f7808d457a5ec59dc74fd04b5097dd5f1bc4447ac32502"
BLOCK4 = Block(
    version=1,
    prev_block_hash=BLOCK3_ID,
    timestamp=1_501_823_700,
    bits="1e0fffff",
    nonce=BLOCK4_VALID_NONCE - 1,  # one less than the real nonce
)
BLOCK4.txns = [COINBASE4, TRANSACTION1, TRANSACTION2]
BLOCK4_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@00000578d1a91048c47504b694eb50568550c55f0c9470002b79ff7889e49ee8\xa9timestamp\xceY\x84\x02\xd4\xa4bits\xa81e0fffff\xa5nonce\xce\x00\nI\xa8\xa4txns\x93\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa14\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcf\x00\x00\x00\x01*\x05\xf2\x00\xaato_address\xd9*00112c3926e5e63ef39aae10a1b5cf0f57f54d6752\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@4543907dbea254f6db47a012f14396027061eeb728a7cb846fe6d9590a3f2e09\x00\xaaunlock_sig\xda\x01\x0480c6092f3dce23e1cf334f7d38bb05090253f54b2b92b1fcd670c4f3705dc2029580e1702b39d3457bb8c7e3292fa47f51d3e5af73be8e169ea73a88b5ddf994308079b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcd\t\xd0\xaato_address\xd9*00b80ffa0c3ff87a882e002ef9dedeed773caf367d\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@4543907dbea254f6db47a012f14396027061eeb728a7cb846fe6d9590a3f2e09\x01\xaaunlock_sig\xda\x01\x0480b8335f155ee93b835ccf0d5aa96fd53146185a1e7d80d3621f5e31d0b1a83185edf7638b6511af8faae029cb4b5be346cb3be8980ca5d98d92bb518a36cc2cf3807b11afeeb5e0a40d14541774c5cf8db6c22dfc98594ca880270fe6fc12f29da564d90f3cc829e18d1879388dacc931fbbc43fa1c4479f4798cf1c82da103e398\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xce\x00\x98\x96\x80\xaato_address\xd9*00cf8e60813d2a07eb6cd06de307ea8baab3e02d60\xa8locktime\x00"

# --------------- BLOCK 5 ---------------
BLOCK5_VALID_NONCE = 1_727_402
BLOCK5_ID = "00000191f69284a6cf58b804b360f49054863ec3614d07f1ac557cf6ffc31b6e"
BLOCK5 = Block(
    version=1,
    prev_block_hash=BLOCK4_ID,
    timestamp=1_501_824_100,
    bits="1e0fffff",
    nonce=BLOCK5_VALID_NONCE - 1,  # one less than the real nonce
)
BLOCK5.txns = [COINBASE5, TRANSACTION3, TRANSACTION4, TRANSACTION5]
BLOCK5_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@00000ee226beddff76805121a46e36308616ead473402c2ca05a47e20118b6a1\xa9timestamp\xceY\x84\x04d\xa4bits\xa81e0fffff\xa5nonce\xce\x00\x12\x81!\xa4txns\x94\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa15\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcf\x00\x00\x00\x01*\x05\xf2\x00\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@4543907dbea254f6db47a012f14396027061eeb728a7cb846fe6d9590a3f2e09\x02\xaaunlock_sig\xda\x01\x04805ca938bb968991c1a5263ea8cb6ed1c988834a77f8916f6626bb2bc3eb75aee282a1c6c389e14a0fd7c62f1d945499c50908062fc1440f866ba766befaa4322980cd1aee50b5e08b2b9512ed72c6aefbb35f762512b05a9716a697ac631afed91f82adffae311dcb1a7e54f688c099bd489fd1e3e3aed011009cbf6bb4c2816ddf\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xce\x0b\xeb\xc2\x00\xaato_address\xd9*00b80ffa0c3ff87a882e002ef9dedeed773caf367d\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@80c7591a9d2ec468b7de394d1160cb5c8f82c5f12146743609a36f6af26fcef1\x00\xaaunlock_sig\xda\x01\x0480657975be2c02556e31ce9b27e6f1ab2646bbfc87a1933878f32281de9790c9016d2be423e362ef85aed1ab3e8cb61b30b22ce4401acfe1da8bb8498f5fdb560a8079b043fbab0aa455d0fd9a38f1befcf1c7116feedd7407f42fcf4ad321e4710014740c3c370109a585debfb082d0889b99fa74708c3f41f0b3d39498cb65b3ee\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xce\x00\x07\xc80\xaato_address\xd9*00cf8e60813d2a07eb6cd06de307ea8baab3e02d60\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@d7d6df59db842aee08218630b98175089437dab165e893f32e48fbd39d8c6d6c\x00\xaaunlock_sig\xda\x01\x0480030d8fcdadb846624a98a850e3a8a9b44dd347e7ebce2569c2aefbd7faa79e6aec8d3ab536f59e4177faccfd68bca2af4cda50b4e33ed1c3e9c6b1ad40e9dbc9805c440bc46d316dbb244bb57e39142f13a1ca7e02d27d46e5cf90fdb98eaf5c1eab11c4af165e4ce3eb0652f8d937620804fe15201c00a7466f56237810988db1\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xce\x00\x07\xc80\xaato_address\xd9*00b80ffa0c3ff87a882e002ef9dedeed773caf367d\xa8locktime\x00"

# --------------- BLOCK 6 ---------------
BLOCK6_VALID_NONCE = 3_252_909
BLOCK6_ID = "00000c9d90f57b09f639902856dfd4e31173290b522c65d526b72e11393287fd"
BLOCK6 = Block(
    version=1,
    prev_block_hash=BLOCK5_ID,
    timestamp=1_501_824_500,
    bits="1e0fffff",
    nonce=BLOCK6_VALID_NONCE - 1,  # one less than the real nonce
)
BLOCK6.txns = [COINBASE6, TRANSACTION6]
BLOCK6_SERIALISED = b"\x86\xa7version\x01\xafprev_block_hash\xd9@0000051a82dd7ab3ae498b7a4070450925a11d0c6aa6737fadc740038ad9f8fd\xa9timestamp\xceY\x84\x05\xf4\xa4bits\xa81e0fffff\xa5nonce\xce\x00 \r/\xa4txns\x92\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@0000000000000000000000000000000000000000000000000000000000000000\xa8ffffffff\xaaunlock_sig\xa16\xa8sequence\x00\xa6txouts\x91\x82\xa5value\xcf\x00\x00\x00\x01*\x05\xf2\x00\xaato_address\xd9*00112c3926e5e63ef39aae10a1b5cf0f57f54d6752\xa8locktime\x00\x84\xa7version\x01\xa5txins\x91\x83\xa8to_spend\x92\xd9@f422efbd54b52696a86e11625ec8d7aaf7f9c88fba01605cd71e08a8c09bf1cc\x00\xaaunlock_sig\xda\x01\x0480b1eb302b6f5bbbd8b970800c63a1e8c285ab06fe7cfe0d3721969ac4707a7b31028c07676936144b9dc0ac71fc0edbefcc76dcaf7e61f5963e9da669eaa1aa7980f4b076bfcdb1f782018d2e3afa195ae1c92f18b3f97ba0ca1a9923bd48291817f8ba9a2dbe2fd347b5a75998221022a548c9bfb326704c021870ccce90c6e1df\xa8sequence\x00\xa6txouts\x94\x82\xa5value\xce\x00\x01\xad\xb0\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b\x82\xa5value\xce\x00\x02I\xf0\xaato_address\xd9*00112c3926e5e63ef39aae10a1b5cf0f57f54d6752\x82\xa5value\xcd\xc3P\xaato_address\xd9*00827c5733e1401c1daaaaa3739ed5ad2acfd9ce4a\x82\xa5value\xce\x00\x02\xab\x98\xaato_address\xd9*0087a6532f90c45ef5cfdd7f90948b2a0fc383dd1b\xa8locktime\x00"
