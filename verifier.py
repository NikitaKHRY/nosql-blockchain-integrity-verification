# verifier.py

from typing import Dict, List

from config import NODE_NAMES, PRIMARY_NODE


class Verifier:
    @staticmethod
    def _hash_event_without_stored_hash(cluster, event_doc: dict) -> str:
        payload = dict(event_doc)
        payload.pop("_id", None)
        payload.pop("event_hash", None)
        return cluster._hash_payload(payload)

    def verify_event_log(self, cluster) -> bool:
        ok = True
        events = list(cluster.event_log.find({}, {"_id": 0}).sort("ts", 1))

        print("\n=== EVENT LOG VERIFICATION ===")
        for event in events:
            stored_hash = event.get("event_hash")
            calculated_hash = self._hash_event_without_stored_hash(cluster, event)
            if stored_hash != calculated_hash:
                ok = False
                print("EVENT LOG TAMPERING DETECTED")
                print(event)
            else:
                print(f"OK: {event['operation']} on record {event['record_id']}")
        return ok

    def verify_chain(self, blockchain) -> bool:
        print("\n=== CHAIN VERIFICATION ===")
        valid = blockchain.is_chain_valid()
        print(f"Blockchain valid: {valid}")
        return valid

    def verify_latest_snapshot(self, cluster, blockchain) -> bool:
        print("\n=== LATEST SNAPSHOT VERIFICATION ===")
        latest_block = blockchain.latest_block()
        current_hashes = cluster.cluster_snapshot_hashes()

        ok = True
        for node in NODE_NAMES:
            expected = latest_block.snapshot_hashes.get(node)
            current = current_hashes.get(node)
            if expected != current:
                ok = False
                print(f"SNAPSHOT MISMATCH ON {node}")
                print(f"expected: {expected}")
                print(f"current : {current}")
            else:
                print(f"OK: {node}")

        return ok

    def compare_nodes(self, cluster) -> bool:
        print("\n=== NODE DIVERGENCE CHECK ===")
        hashes = cluster.cluster_snapshot_hashes()
        reference = hashes[PRIMARY_NODE]
        ok = True

        for node, h in hashes.items():
            if h != reference:
                ok = False
                print(f"NODE DIVERGENCE: {node} differs from {PRIMARY_NODE}")
            else:
                print(f"OK: {node}")

        return ok

    def detect_missing_records(self, cluster, reference_node: str = PRIMARY_NODE) -> bool:
        print("\n=== MISSING RECORD CHECK ===")
        reference_ids = {doc["id"] for doc in cluster.get_node_records(reference_node)}
        ok = True

        for node in NODE_NAMES:
            current_ids = {doc["id"] for doc in cluster.get_node_records(node)}
            missing = sorted(reference_ids - current_ids)
            if missing:
                ok = False
                print(f"{node}: missing records -> {missing}")
            else:
                print(f"{node}: no missing records")

        return ok

    def full_audit(self, cluster, blockchain) -> Dict[str, bool]:
        results = {
            "chain_valid": self.verify_chain(blockchain),
            "event_log_valid": self.verify_event_log(cluster),
            "latest_snapshot_ok": self.verify_latest_snapshot(cluster, blockchain),
            "nodes_consistent": self.compare_nodes(cluster),
            "missing_records_ok": self.detect_missing_records(cluster),
        }

        print("\n=== AUDIT SUMMARY ===")
        for k, v in results.items():
            print(f"{k}: {v}")

        return results