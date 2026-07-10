# data_generator.py

import csv
import random
from pathlib import Path

NAMES = [
    "Ivan", "Anna", "Petro", "Olha", "Maria", "Andrii", "Sofiia", "Danylo",
    "Iryna", "Nazar", "Oksana", "Vlad", "Kateryna", "Yehor", "Polina",
    "Maksym", "Yulia", "Taras", "Lilia", "Artem"
]

CITIES = [
    "Kyiv", "Lviv", "Kharkiv", "Dnipro", "Odesa", "Poltava",
    "Vinnytsia", "Zaporizhzhia", "Chernihiv", "Ivano-Frankivsk"
]

ACCOUNT_TYPES = ["student", "basic", "premium", "business"]

def generate_sample_csv(path: str, n: int = 120, seed: int = 42) -> None:
    random.seed(seed)
    path_obj = Path(path)

    rows = []
    for i in range(1, n + 1):
        row = {
            "id": i,
            "name": random.choice(NAMES) + f"_{i}",
            "balance": random.randint(50, 5000),
            "city": random.choice(CITIES),
            "account_type": random.choice(ACCOUNT_TYPES),
            "status": random.choice(["active", "active", "active", "suspended"]),
        }
        rows.append(row)

    with path_obj.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "name", "balance", "city", "account_type", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)