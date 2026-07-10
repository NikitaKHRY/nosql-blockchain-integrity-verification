# merkle.py

import hashlib
from typing import List


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merkle_root(hashes: List[str]) -> str:
    if not hashes:
        return _sha256("EMPTY")

    level = hashes[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        next_level = []
        for i in range(0, len(level), 2):
            next_level.append(_sha256(level[i] + level[i + 1]))
        level = next_level

    return level[0]