# main.py

import random

from attacks import (
    simulate_illegal_deletion,
    simulate_illegal_modification,
    simulate_node_failure,
    simulate_node_recovery,
)
from blockchain import BlockchainLedger
from cluster import DistributedNoSQLCluster
from config import BATCH_SIZE, DATA_FILE, PRIMARY_NODE
from data_generator import generate_sample_csv
from experiments import run_latency_experiment
from verifier import Verifier

def make_legitimate_activity(cluster, blockchain):
    print("\n=== LEGITIMATE OPERATIONS ===")

    random.seed(21)
    sample_ids = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

    ops_done = 0

    for rid in sample_ids[:4]:
        event_hash = cluster.update_record(
            rid,
            {"balance": random.randint(500, 8000)},
            log_event=True,
        )
        blockchain.queue_event(event_hash)
        ops_done += 1

    cluster.create_record(
        {
            "id": 1001,
            "name": "New_User_1001",
            "balance": 1200,
            "city": "Kyiv",
            "account_type": "premium",
            "status": "active",
        }
    )
    event_hash = cluster.event_log.find_one(
        {"record_id": 1001},
        {"_id": 0, "event_hash": 1}
    )["event_hash"]
    blockchain.queue_event(event_hash)
    ops_done += 1

    cluster.create_record(
        {
            "id": 1002,
            "name": "New_User_1002",
            "balance": 2400,
            "city": "Lviv",
            "account_type": "business",
            "status": "active",
        }
    )
    event_hash = cluster.event_log.find_one(
        {"record_id": 1002},
        {"_id": 0, "event_hash": 1}
    )["event_hash"]
    blockchain.queue_event(event_hash)
    ops_done += 1

    cluster.delete_record(19, log_event=True)
    event_hash = cluster.event_log.find_one(
        {"operation": "delete", "record_id": 19},
        {"_id": 0, "event_hash": 1}
    )["event_hash"]
    blockchain.queue_event(event_hash)
    ops_done += 1

    for rid in sample_ids[4:7]:
        event_hash = cluster.update_record(
            rid,
            {"status": "active", "balance": random.randint(1000, 6000)},
            log_event=True,
        )
        blockchain.queue_event(event_hash)
        ops_done += 1

    if blockchain.pending_event_hashes:
        blockchain.commit_batch(
            cluster.cluster_snapshot_hashes(),
            batch_label="checkpoint_1"
        )

    print(f"Legitimate operations completed: {ops_done}")

def print_cluster_state(cluster):
    print("\n=== CLUSTER STATE ===")
    report = cluster.current_state_report()
    for node, info in report.items():
        print(
            f"{node}: online={info['online']}, "
            f"count={info['count']}, "
            f"snapshot={info['snapshot_hash'][:16]}..."
        )

if __name__ == "__main__":
    generate_sample_csv(DATA_FILE, n=120, seed=42)

    cluster = DistributedNoSQLCluster()
    blockchain = BlockchainLedger(cluster.db)
    verifier = Verifier()

    cluster.reset()
    blockchain.reset()
    cluster.bootstrap_from_csv(DATA_FILE)

    print_cluster_state(cluster)
    make_legitimate_activity(cluster, blockchain)

    print("\n=== BLOCKCHAIN AFTER LEGITIMATE OPERATIONS ===")
    blockchain.print_chain()

    print("\n=== AUDIT BEFORE ATTACK ===")
    verifier.full_audit(cluster, blockchain)

    simulate_node_failure(cluster, "node_3")
    cluster.update_record(7, {"balance": 7777}, log_event=True, target_nodes=["node_1", "node_2"])
    blockchain.queue_event(
        cluster.event_log.find_one(
            {"operation": "update", "record_id": 7},
            {"_id": 0, "event_hash": 1}
        )["event_hash"]
    )

    simulate_illegal_modification(cluster, "node_2", 5, {"balance": 999999})
    simulate_illegal_deletion(cluster, "node_2", 11)

    print_cluster_state(cluster)

    print("\n=== AUDIT AFTER ATTACK ===")
    verifier.full_audit(cluster, blockchain)

    simulate_node_recovery(cluster, "node_3", authority_node=PRIMARY_NODE)
    simulate_node_recovery(cluster, "node_2", authority_node=PRIMARY_NODE)

    if blockchain.pending_event_hashes:
        blockchain.commit_batch(
            cluster.cluster_snapshot_hashes(),
            batch_label="recovery_checkpoint"
        )
    else:
        blockchain.commit_batch(
            cluster.cluster_snapshot_hashes(),
            batch_label="recovery_checkpoint"
        )

    print("\n=== AUDIT AFTER RECOVERY ===")
    verifier.full_audit(cluster, blockchain)

    print("\n=== LATENCY BENCHMARK ===")
    run_latency_experiment(iterations=30, batch_size=BATCH_SIZE)
