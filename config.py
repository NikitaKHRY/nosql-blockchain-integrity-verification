# config.py

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "distributed_nosql_blockchain_db"

NODE_NAMES = ["node_1", "node_2", "node_3"]
NODE_COLLECTION_SUFFIX = "_docs"

EVENT_LOG_COLLECTION = "audit_events"
BLOCKCHAIN_COLLECTION = "audit_chain"

DATA_FILE = "users.csv"

PRIMARY_NODE = "node_1"
BATCH_SIZE = 8