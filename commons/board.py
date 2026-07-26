"""Filesystem board for lightweight agent communication."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import board_dir, ensure_base_dirs


BOARD_SUBDIRS = ("agents", "tasks", "plans", "messages", "inbox", "leases", "audit")


def ensure_board() -> Path:
    ensure_base_dirs()
    root = board_dir()
    for name in BOARD_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def publish(kind: str, item_id: str, payload: Any) -> Path:
    root = ensure_board()
    path = root / kind / f"{item_id}.json"
    write_json_atomic(path, payload)
    return path


def publish_agent(agent: dict[str, Any]) -> None:
    publish("agents", agent["agent_id"], agent)


def publish_task(task: dict[str, Any]) -> None:
    publish("tasks", task["task_id"], task)


def publish_plan(plan: dict[str, Any]) -> None:
    publish("plans", plan["plan_id"], plan)


def publish_message(message: dict[str, Any]) -> None:
    root = ensure_board()
    publish("messages", message["message_id"], message)
    recipient = message.get("recipient_agent_id") or "broadcast"
    write_json_atomic(root / "inbox" / recipient / f"{message['message_id']}.json", message)


def publish_lease(lease: dict[str, Any]) -> None:
    publish("leases", lease["lease_id"], lease)


def publish_status(status: dict[str, Any]) -> None:
    root = ensure_board()
    write_json_atomic(root / "status.json", status)


def publish_audit_event(event: dict[str, Any]) -> None:
    root = ensure_board()
    append_jsonl(root / "audit" / "events.jsonl", event)


def board_path() -> str:
    return str(ensure_board())

