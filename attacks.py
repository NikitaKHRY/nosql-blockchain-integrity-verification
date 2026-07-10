# attacks.py

def simulate_illegal_modification(cluster, node_name: str, record_id: int, new_fields: dict) -> None:
    print(f"\n[ATTACK] illegal modification on {node_name}, record {record_id}")
    cluster.direct_tamper_update(node_name, record_id, new_fields)


def simulate_illegal_deletion(cluster, node_name: str, record_id: int) -> None:
    print(f"\n[ATTACK] illegal deletion on {node_name}, record {record_id}")
    cluster.direct_tamper_delete(node_name, record_id)


def simulate_node_failure(cluster, node_name: str) -> None:
    print(f"\n[FAILURE] node {node_name} goes offline")
    cluster.set_node_status(node_name, False)


def simulate_node_recovery(cluster, node_name: str, authority_node: str = None) -> None:
    print(f"\n[RECOVERY] node {node_name} restored from authority state")
    synced = cluster.repair_node(node_name, authority_node=authority_node)
    print(f"{node_name} synchronized with {synced} records")