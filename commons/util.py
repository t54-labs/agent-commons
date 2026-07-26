"""Small shared utilities."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def now_ts() -> float:
    return time.time()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_event(prev_hash: str, event_type: str, payload: dict[str, Any], created_at: str) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(b"\0")
    h.update(event_type.encode("utf-8"))
    h.update(b"\0")
    h.update(created_at.encode("utf-8"))
    h.update(b"\0")
    h.update(json_dumps(payload).encode("utf-8"))
    return h.hexdigest()


def infer_repo(path: Path) -> str | None:
    current = path.resolve()
    while True:
        if (current / ".git").exists():
            return str(current)
        if current.parent == current:
            return None
        current = current.parent


def hostname() -> str:
    return socket.gethostname()


def current_pid() -> int:
    return os.getpid()


def seconds_from_ttl(ttl: str | None, default_seconds: int = 1800) -> int:
    if not ttl:
        return default_seconds
    raw = ttl.strip().lower()
    if raw.isdigit():
        return int(raw)
    unit = raw[-1]
    number = raw[:-1]
    if not number.isdigit():
        raise ValueError(f"invalid ttl: {ttl}")
    n = int(number)
    if unit == "s":
        return n
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    if unit == "d":
        return n * 86400
    raise ValueError(f"invalid ttl: {ttl}")

