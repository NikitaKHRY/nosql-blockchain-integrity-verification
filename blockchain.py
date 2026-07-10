# blockchain.py

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

from merkle import merkle_root
from config import BLOCKCHAIN_COLLECTION, NODE_NAMES

class Block:
    def __init__(
        self,
        index: int,
        timestamp: str,
        batch_label: str,
        event_hashes: List[str],
        snapshot_hashes: Dict[str, str],
        merkle_root_value: str,
        previous_hash: str,
    ):
        self.index = index
        self.timestamp = timestamp
        self.batch_label = batch_label
        self.event_hashes = event_hashes
        self.snapshot_hashes = snapshot_hashes
        self.merkle_root_value = merkle_root_value
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "batch_label": self.batch_label,
            "event_hashes": self.event_hashes,
            "snapshot_hashes": self.snapshot_hashes,
            "merkle_root_value": self.merkle_root_value,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    def calculate_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "batch_label": self.batch_label,
            "event_hashes": self.event_hashes,
            "snapshot_hashes": self.snapshot_hashes,
            "merkle_root_value": self.merkle_root_value,
            "previous_hash": self.previous_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class BlockchainLedger:
    def __init__(self, db):
        self.collection = db[BLOCKCHAIN_COLLECTION]
        self.chain: List[Block] = [self._create_genesis_block()]
        self.pending_event_hashes: List[str] = []

    def reset(self) -> None:
        self.collection.delete_many({})
        self.chain = [self._create_genesis_block()]
        self.pending_event_hashes = []

    def _create_genesis_block(self) -> Block:
        return Block(
            index=0,
            timestamp=str(datetime.utcnow()),
            batch_label="GENESIS",
            event_hashes=["0"],
            snapshot_hashes={node: "0" for node in NODE_NAMES},
            merkle_root_value="0",
            previous_hash="0",
        )

    def latest_block(self) -> Block:
        return self.chain[-1]

    def queue_event(self, event_hash: str) -> None:
        if event_hash:
            self.pending_event_hashes.append(event_hash)

    def commit_batch(
        self,
        snapshot_hashes: Dict[str, str],
        batch_label: str,
        event_hashes: Optional[List[str]] = None,
    ) -> Optional[Block]:
        if event_hashes is None:
            event_hashes = self.pending_event_hashes[:]

        combined = list(event_hashes) + [snapshot_hashes[node] for node in sorted(snapshot_hashes)]
        root = merkle_root(combined)

        previous_hash = self.latest_block().hash
        block = Block(
            index=len(self.chain),
            timestamp=str(datetime.utcnow()),
            batch_label=batch_label,
            event_hashes=list(event_hashes),
            snapshot_hashes=dict(snapshot_hashes),
            merkle_root_value=root,
            previous_hash=previous_hash,
        )
        self.chain.append(block)
        self.collection.insert_one(block.to_dict())
        self.pending_event_hashes = []
        return block

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

    def blocks(self) -> List[dict]:
        return [block.to_dict() for block in self.chain]

    def print_chain(self) -> None:
        print("\n=== BLOCKCHAIN LEDGER ===")
        for block in self.chain:
            print(f"Index: {block.index}")
            print(f"Label: {block.batch_label}")
            print(f"Time: {block.timestamp}")
            print(f"Merkle root: {block.merkle_root_value}")
            print(f"Hash: {block.hash}")
            print(f"Prev: {block.previous_hash}")
            print("-" * 60)