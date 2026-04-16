"""
Mining node: integrates P2P networking with block mining.

Runs PoW in a thread pool so it doesn't block the asyncio event loop.
When a new block arrives from a peer, mining is interrupted and restarted.
"""

import asyncio
import logging
import threading
import time

from luracoin.blocks import Block
from luracoin.config import Config
from luracoin.genesis import initialize_chain
from luracoin.helpers import mining_reward
from luracoin.pow import proof_of_work
from luracoin.transactions import Transaction
from luracoin.network.node import Node

log = logging.getLogger(__name__)


class MiningNode:
    """
    Full node that mines blocks and participates in the P2P network.

    - Starts P2P server and connects to seeds
    - Mines blocks in a background thread (interruptible PoW)
    - Broadcasts mined blocks to peers
    - Stops mining when a peer's block arrives at our expected height
    - Listens to peers for blocks/transactions continuously
    """

    def __init__(self, address: str, port: int = None, seed_nodes: list = None):
        self.address = address
        self.node = Node(
            port=port or Config.PORT,
            seed_nodes=seed_nodes,
        )
        self._stop_mining_event = threading.Event()
        self._running = False

    async def start(self) -> None:
        """Initialize chain, start P2P, and begin mining."""
        initialize_chain()

        # Set callback so node notifies us when a peer's block arrives
        self.node.on_new_block = self._on_peer_block

        await self.node.start()
        self._running = True

        # Connect to seeds in background
        asyncio.create_task(self._connect_and_discover())

        # Start mining loop
        await self._mining_loop()

    async def stop(self) -> None:
        self._running = False
        self._stop_mining_event.set()
        await self.node.stop()

    def _on_peer_block(self) -> None:
        """Called by Node when a valid block is received from a peer."""
        log.info("New block from peer, interrupting mining")
        self._stop_mining_event.set()

    async def _connect_and_discover(self) -> None:
        """Connect to seed nodes and periodically discover new peers."""
        await self.node.connect_to_seeds()

        while self._running:
            await asyncio.sleep(30)
            if self._running:
                await self.node.connect_to_seeds()

    async def _mining_loop(self) -> None:
        """Main mining loop: build block, run PoW, broadcast, repeat."""
        loop = asyncio.get_event_loop()

        while self._running:
            self._stop_mining_event.clear()

            # Build the block template
            block = self._build_block_template()
            if block is None:
                await asyncio.sleep(1)
                continue

            # Run PoW in thread pool (non-blocking)
            nonce = await loop.run_in_executor(
                None, self._mine_block, block
            )

            if nonce == -1:
                # Mining was interrupted by a peer's block
                log.info("Mining interrupted, restarting with new tip")
                continue

            # Block mined successfully
            block.save()
            log.info(f"Mined block {block.height} | nonce: {block.nonce}")
            print(f"Mined block {block.height} | nonce: {block.nonce}")

            # Broadcast to peers
            await self.node.broadcast_block(block)

    def _build_block_template(self) -> Block:
        """Create a block template ready for PoW."""
        chain = self.node.chain

        prev_block = Block.get(chain.tip)
        height = chain.tip + 1 if prev_block else 0
        prev_hash = prev_block.id if prev_block else "0" * 64

        # Select transactions from mempool
        block = Block(miner=self.address, height=height)
        try:
            block.select_transactions()
        except Exception:
            block.txns = []

        # Add coinbase
        total_fees = sum(txn.fee for txn in block.txns)
        coinbase = Transaction(
            chain=0,
            nonce=0,
            fee=0,
            value=mining_reward(height) + total_fees,
            from_address="0" * 34,
            to_address=self.address,
            unlock_sig=Config.COINBASE_UNLOCK_SIGNATURE,
        )
        block.txns.insert(0, coinbase)

        block.version = 1
        block.prev_block_hash = prev_hash
        block.timestamp = int(time.time())
        block.bits = Config.STARTING_DIFFICULTY
        block.nonce = 0

        return block

    def _mine_block(self, block: Block) -> int:
        """Run PoW (called in thread pool). Returns nonce or -1 if interrupted."""
        return proof_of_work(block, stop_event=self._stop_mining_event)
