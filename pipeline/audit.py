"""Append only, hash chained audit log. Tamper evident.

Every editorial decision is recorded. Each entry's hash includes the previous
entry's hash, so any retroactive edit breaks the chain and is detectable. This
is both the legal defense and the public trust proof.
"""
from __future__ import annotations
import json
import hashlib
import os
from datetime import datetime, timezone

GENESIS = "0" * 64


def _hash_entry(entry: dict) -> str:
    payload = json.dumps({k: entry[k] for k in entry if k != "hash"},
                         sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _last_entry(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    last = None
    with open(path) as f:
        for line in f:
            if line.strip():
                last = json.loads(line)
    return last


def append(path: str, story_id: str, decision: str, reasons: list[str], sources: list[str]) -> dict:
    prev = _last_entry(path)
    prev_hash = prev["hash"] if prev else GENESIS
    seq = (prev["seq"] + 1) if prev else 0
    entry = {
        "seq": seq,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "story_id": story_id,
        "decision": decision,
        "reasons": reasons,
        "sources": sources,
        "prev_hash": prev_hash,
    }
    entry["hash"] = _hash_entry(entry)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def verify_chain(path: str) -> bool:
    """True if the chain is intact (no tampering)."""
    prev_hash = GENESIS
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry["prev_hash"] != prev_hash:
                return False
            if _hash_entry(entry) != entry["hash"]:
                return False
            prev_hash = entry["hash"]
    return True
