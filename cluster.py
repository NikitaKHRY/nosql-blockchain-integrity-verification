# cluster.py

import copy
import csv
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import MongoClient

from config import (
    BLOCKCHAIN_COLLECTION,
    DB_NAME,
    EVENT_LOG_COLLECTION,
    MONGO_URI,
    NODE_COLLECTION_SUFFIX,
    NODE_NAMES,
    PRIMARY_NODE,
)


class DistributedNoSQLCluster:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]

        self.node_collections = {
            node: self.db[f"{node}{NODE_COLLECTION_SUFFIX}"]
            for node in NODE_NAMES
        }
        self.event_log = self.db[EVENT_LOG_COLLECTION]

        self.node_status = {node: True for node in NODE_NAMES}

    @staticmethod
    def _canonical_json(obj) -> str:
        return json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _hash_payload(cls, payload) -> str:
        data = cls._canonical_json(payload).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _normalize_record(record: dict) -> dict:
        normalized = dict(record)
        normalized["id"] = int(normalized["id"])
        normalized["balance"] = int(normalized["balance"])
        normalized["name"] = str(normalized["name"])
        normalized["city"] = str(normalized["city"])
        normalized["account_type"] = str(normalized["account_type"])
        normalized["status"] = str(normalized["status"])
        return normalized

    def reset(self) -> None:
        for collection in self.node_collections.values():
            collection.delete_many({})
        self.event_log.delete_many({})
        self.node_status = {node: True for node in NODE_NAMES}

    def bootstrap_from_csv(self, csv_path: str) -> List[dict]:
        records = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(self._normalize_record(row))

        for node_name, collection in self.node_collections.items():
            collection.delete_many({})
            if records:
                collection.insert_many(copy.deepcopy(records))

        self.event_log.delete_many({})
        return records

    def set_node_status(self, node_name: str, online: bool) -> None:
        if node_name not in self.node_status:
            raise ValueError(f"Unknown node: {node_name}")
        self.node_status[node_name] = online

    def online_nodes(self) -> List[str]:
        return [node for node, active in self.node_status.items() if active]

    def get_node_records(self, node_name: str) -> List[dict]:
        if node_name not in self.node_collections:
            raise ValueError(f"Unknown node: {node_name}")
        return list(self.node_collections[node_name].find({}, {"_id": 0}))

    def get_record(self, node_name: str, record_id: int) -> Optional[dict]:
        return self.node_collections[node_name].find_one({"id": int(record_id)}, {"_id": 0})

    def _apply_to_nodes(self, operation_fn, target_nodes: Optional[List[str]] = None) -> List[str]:
        if target_nodes is None:
            target_nodes = self.online_nodes()

        applied_nodes = []
        for node_name in target_nodes:
            if self.node_status.get(node_name, False):
                operation_fn(self.node_collections[node_name])
                applied_nodes.append(node_name)
        return applied_nodes

    def _store_event(self, event_doc: dict) -> str:
        event_hash = self._hash_payload(event_doc)
        event_doc_with_hash = dict(event_doc)
        event_doc_with_hash["event_hash"] = event_hash
        self.event_log.insert_one(event_doc_with_hash)
        return event_hash

    def create_record(
        self,
        record: dict,
        target_nodes: Optional[List[str]] = None,
        source: str = "client",
    ) -> Optional[str]:
        normalized = self._normalize_record(record)

        def op(collection):
            collection.replace_one({"id": normalized["id"]}, normalized, upsert=True)

        applied_nodes = self._apply_to_nodes(op, target_nodes=target_nodes)
        if not applied_nodes:
            return None

        event_doc = {
            "ts": datetime.utcnow().isoformat(),
            "operation": "insert",
            "record_id": normalized["id"],
            "before": None,
            "after": normalized,
            "target_nodes": applied_nodes,
            "source": source,
        }
        return self._store_event(event_doc)

    def update_record(
        self,
        record_id: int,
        updates: dict,
        target_nodes: Optional[List[str]] = None,
        source: str = "client",
        log_event: bool = True,
    ) -> Optional[str]:
        record_id = int(record_id)
        current = self.get_record(PRIMARY_NODE, record_id)
        if current is None:
            raise ValueError(f"Record {record_id} not found on primary node")

        before = copy.deepcopy(current)
        after = copy.deepcopy(current)
        for key, value in updates.items():
            after[key] = value

        after = self._normalize_record(after)

        def op(collection):
            collection.update_one({"id": record_id}, {"$set": updates})

        applied_nodes = self._apply_to_nodes(op, target_nodes=target_nodes)
        if not applied_nodes:
            return None

        if not log_event:
            return ""

        event_doc = {
            "ts": datetime.utcnow().isoformat(),
            "operation": "update",
            "record_id": record_id,
            "before": before,
            "after": after,
            "target_nodes": applied_nodes,
            "source": source,
        }
        return self._store_event(event_doc)

    def delete_record(
        self,
        record_id: int,
        target_nodes: Optional[List[str]] = None,
        source: str = "client",
        log_event: bool = True,
    ) -> Optional[str]:
        record_id = int(record_id)
        current = self.get_record(PRIMARY_NODE, record_id)
        if current is None:
            raise ValueError(f"Record {record_id} not found on primary node")

        before = copy.deepcopy(current)

        def op(collection):
            collection.delete_one({"id": record_id})

        applied_nodes = self._apply_to_nodes(op, target_nodes=target_nodes)
        if not applied_nodes:
            return None

        if not log_event:
            return ""

        event_doc = {
            "ts": datetime.utcnow().isoformat(),
            "operation": "delete",
            "record_id": record_id,
            "before": before,
            "after": None,
            "target_nodes": applied_nodes,
            "source": source,
        }
        return self._store_event(event_doc)

    def direct_tamper_update(self, node_name: str, record_id: int, updates: dict) -> None:
        if node_name not in self.node_collections:
            raise ValueError(f"Unknown node: {node_name}")
        if not self.node_status.get(node_name, False):
            raise RuntimeError(f"Node {node_name} is offline")

        self.node_collections[node_name].update_one({"id": int(record_id)}, {"$set": updates})

    def direct_tamper_delete(self, node_name: str, record_id: int) -> None:
        if node_name not in self.node_collections:
            raise ValueError(f"Unknown node: {node_name}")
        if not self.node_status.get(node_name, False):
            raise RuntimeError(f"Node {node_name} is offline")

        self.node_collections[node_name].delete_one({"id": int(record_id)})

    def repair_node(self, node_name: str, authority_node: Optional[str] = None) -> int:
        if node_name not in self.node_collections:
            raise ValueError(f"Unknown node: {node_name}")

        if authority_node is None:
            online = self.online_nodes()
            authority_node = PRIMARY_NODE if PRIMARY_NODE in online else (online[0] if online else PRIMARY_NODE)

        source_records = self.get_node_records(authority_node)
        collection = self.node_collections[node_name]
        collection.delete_many({})
        if source_records:
            collection.insert_many(copy.deepcopy(source_records))

        self.node_status[node_name] = True
        return len(source_records)

    def snapshot_hash(self, node_name: str) -> str:
        records = self.get_node_records(node_name)
        sorted_records = sorted(records, key=lambda x: x["id"])
        return self._hash_payload(sorted_records)

    def cluster_snapshot_hashes(self) -> Dict[str, str]:
        return {node: self.snapshot_hash(node) for node in NODE_NAMES}

    def current_state_report(self) -> dict:
        report = {}
        for node in NODE_NAMES:
            records = self.get_node_records(node)
            report[node] = {
                "online": self.node_status[node],
                "count": len(records),
                "snapshot_hash": self.snapshot_hash(node),
            }
        return report

    def event_log_records(self) -> List[dict]:
        return list(self.event_log.find({}, {"_id": 0}))