# experiments.py

import random
import time

from blockchain import BlockchainLedger
from cluster import DistributedNoSQLCluster
from config import BATCH_SIZE, DATA_FILE
from data_generator import generate_sample_csv

def run_latency_experiment(iterations: int = 30, batch_size: int = BATCH_SIZE) -> None:
    print("\n=== LATENCY EXPERIMENT ===")

    generate_sample_csv(DATA_FILE, n=120, seed=42)

    # Baseline: writes without audit logging
    cluster_1 = DistributedNoSQLCluster()
    blockchain_1 = BlockchainLedger(cluster_1.db)
    cluster_1.reset()
    blockchain_1.reset()
    cluster_1.bootstrap_from_csv(DATA_FILE)

    ids = [doc["id"] for doc in cluster_1.get_node_records("node_1")]
    random.seed(7)

    start = time.perf_counter()
    for i in range(iterations):
        rid = random.choice(ids)
        new_balance = random.randint(100, 9000)
        cluster_1.update_record(rid, {"balance": new_balance}, log_event=False)
    baseline_time = time.perf_counter() - start

    # Secure mode: writes + event log + blockchain batching
    cluster_2 = DistributedNoSQLCluster()
    blockchain_2 = BlockchainLedger(cluster_2.db)
    cluster_2.reset()
    blockchain_2.reset()
    cluster_2.bootstrap_from_csv(DATA_FILE)

    ids = [doc["id"] for doc in cluster_2.get_node_records("node_1")]
    random.seed(7)

    start = time.perf_counter()
    for i in range(iterations):
        rid = random.choice(ids)
        new_balance = random.randint(100, 9000)
        event_hash = cluster_2.update_record(rid, {"balance": new_balance}, log_event=True)
        blockchain_2.queue_event(event_hash)

        if (i + 1) % batch_size == 0:
            blockchain_2.commit_batch(
                cluster_2.cluster_snapshot_hashes(),
                batch_label=f"batch_{(i + 1) // batch_size}"
            )

    if blockchain_2.pending_event_hashes:
        blockchain_2.commit_batch(
            cluster_2.cluster_snapshot_hashes(),
            batch_label="final_batch"
        )

    secure_time = time.perf_counter() - start

    overhead = secure_time - baseline_time
    overhead_pct = (overhead / baseline_time * 100) if baseline_time > 0 else 0

    print(f"Baseline writes time: {baseline_time:.4f} s")
    print(f"Secure mode time    : {secure_time:.4f} s")
    print(f"Overhead            : {overhead:.4f} s")
    print(f"Overhead %          : {overhead_pct:.2f} %")