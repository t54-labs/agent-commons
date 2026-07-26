"""SQLite storage and transaction helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .paths import db_path, ensure_base_dirs


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  name TEXT,
  runtime TEXT NOT NULL,
  runtime_version TEXT,
  host TEXT,
  pid INTEGER,
  workspace TEXT,
  repo TEXT,
  branch TEXT,
  task_id TEXT,
  capabilities TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'online',
  registered_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  stale_after_seconds INTEGER NOT NULL DEFAULT 90
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  owner_agent_id TEXT,
  summary TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
  plan_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  summary TEXT,
  body TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(task_id, version)
);

CREATE TABLE IF NOT EXISTS message_threads (
  thread_id TEXT PRIMARY KEY,
  task_id TEXT,
  subject TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  task_id TEXT,
  sender_agent_id TEXT,
  recipient_agent_id TEXT,
  message_type TEXT NOT NULL DEFAULT 'note',
  body TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'workspace',
  acked_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(thread_id) REFERENCES message_threads(thread_id)
);

CREATE TABLE IF NOT EXISTS resources (
  resource_id TEXT PRIMARY KEY,
  canonical_id TEXT NOT NULL UNIQUE,
  description TEXT,
  fencing_epoch INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resource_aliases (
  alias TEXT PRIMARY KEY,
  canonical_id TEXT NOT NULL,
  FOREIGN KEY(canonical_id) REFERENCES resources(canonical_id)
);

CREATE TABLE IF NOT EXISTS leases (
  lease_id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  canonical_resource_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  holder_agent_id TEXT,
  reason TEXT,
  state TEXT NOT NULL,
  fencing_epoch INTEGER NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at REAL NOT NULL,
  released_at TEXT,
  FOREIGN KEY(canonical_resource_id) REFERENCES resources(canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_leases_resource_state
  ON leases(canonical_resource_id, state, expires_at);

CREATE TABLE IF NOT EXISTS operations (
  operation_id TEXT PRIMARY KEY,
  lease_id TEXT,
  resource_id TEXT,
  mode TEXT,
  command TEXT,
  state TEXT NOT NULL,
  exit_code INTEGER,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  task_id TEXT,
  artifact_type TEXT NOT NULL,
  visibility TEXT NOT NULL,
  source_path TEXT NOT NULL,
  stored_path TEXT,
  sha256 TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  actor_agent_id TEXT,
  task_id TEXT,
  resource_id TEXT,
  payload TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_outbox (
  event_id INTEGER PRIMARY KEY,
  delivered_at TEXT,
  FOREIGN KEY(event_id) REFERENCES audit_events(event_id)
);

CREATE TABLE IF NOT EXISTS client_requests (
  request_id TEXT PRIMARY KEY,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    ensure_base_dirs()
    conn = sqlite3.connect(path or db_path(), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '1')"
        )


@contextmanager
def transaction(conn: sqlite3.Connection, immediate: bool = True) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
