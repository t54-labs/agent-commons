"""Commons Private Relay state and HTTP server."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import base64
import binascii
import hashlib
import hmac
import re
import shlex
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from contextlib import closing, contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, unquote, urlparse

from .identity import (
    MAX_AGENT_HANDLE_LENGTH,
    IdentityError,
    handle_has_user_prefix,
    profile_from_name,
    qualify_name,
)
from .paths import ensure_base_dirs, relay_db_path
from .http_server import CommonsThreadingHTTPServer
from .service import LEASE_COMPAT
from .util import json_dumps, make_id, now_ts, seconds_from_ttl, utc_now


FENCED_LEASE_MODES = {"write", "exclusive", "maintenance"}
REMOTE_TASK_STATUSES = {
    "created",
    "claimed",
    "in_progress",
    "blocked",
    "needs_human",
    "ready_for_review",
    "completed",
    "cancelled",
    "failed",
}
CONSOLE_COOKIE_NAME = "commons_console_session"
CONSOLE_SESSION_TTL_SECONDS = 12 * 60 * 60
CONSOLE_VILLAGE_AGENT_LIMIT = 12
CONSOLE_VILLAGE_MESSAGE_LIMIT = 12
AGENT_RECENT_SECONDS = 2 * 60
AGENT_ACTIVE_SECONDS = 30 * 60
MAX_REQUEST_BODY_BYTES = 1024 * 1024
MAX_QUERY_LIMIT = 10_000
REQUEST_SOCKET_TIMEOUT_SECONDS = 15
_RELAY_INIT_LOCK = threading.Lock()
_INITIALIZED_RELAY_DBS: dict[str, tuple[int, int]] = {}


def user_prefix_enforcement_enabled() -> bool:
    """Return whether new Relay registrations require human attribution."""
    value = os.environ.get("COMMONS_REQUIRE_USER_PREFIX")
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


RELAY_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS relay_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  handle TEXT,
  contact_code TEXT,
  name TEXT,
  user_name TEXT,
  user_slug TEXT,
  runtime TEXT NOT NULL,
  workspace TEXT,
  task_id TEXT,
  status TEXT NOT NULL DEFAULT 'online',
  registered_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  PRIMARY KEY(project_id, agent_id)
);

CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  sender_agent_id TEXT,
  recipient_agent_id TEXT,
  message_type TEXT NOT NULL DEFAULT 'note',
  audience_policy TEXT NOT NULL DEFAULT 'legacy_registered_at_send',
  body TEXT NOT NULL,
  acked_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_inbox
  ON messages(project_id, recipient_agent_id, acked_at, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_project_sender
  ON messages(project_id, sender_agent_id);

CREATE TABLE IF NOT EXISTS message_audience (
  message_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  delivered_at TEXT NOT NULL,
  PRIMARY KEY(message_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_message_audience_agent
  ON message_audience(agent_id, message_id);

CREATE TABLE IF NOT EXISTS message_receipts (
  message_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  acked_at TEXT NOT NULL,
  PRIMARY KEY(message_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_message_receipts_agent
  ON message_receipts(agent_id, acked_at, message_id);

CREATE INDEX IF NOT EXISTS idx_agents_project_activity
  ON agents(project_id, status, heartbeat_at);

CREATE TABLE IF NOT EXISTS resources (
  project_id TEXT NOT NULL,
  canonical_id TEXT NOT NULL,
  fencing_epoch INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_id, canonical_id)
);

CREATE TABLE IF NOT EXISTS leases (
  lease_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  canonical_resource_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  holder_agent_id TEXT,
  reason TEXT,
  state TEXT NOT NULL,
  fencing_epoch INTEGER NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at REAL NOT NULL,
  released_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_relay_leases_resource_state
  ON leases(project_id, canonical_resource_id, state, expires_at);

CREATE INDEX IF NOT EXISTS idx_relay_leases_project_holder
  ON leases(project_id, holder_agent_id, state, expires_at);

CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  event_type TEXT NOT NULL,
  actor_agent_id TEXT,
  resource_id TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_project_event
  ON audit_events(project_id, event_id DESC);

CREATE INDEX IF NOT EXISTS idx_audit_created_at
  ON audit_events(created_at, event_id DESC);

CREATE INDEX IF NOT EXISTS idx_audit_project_created_at
  ON audit_events(project_id, created_at, event_id DESC);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  owner_agent_id TEXT,
  status TEXT NOT NULL DEFAULT 'created',
  current_step TEXT,
  next_step TEXT,
  blocked_reason TEXT,
  progress_percent INTEGER,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_status
  ON tasks(project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_project_owner
  ON tasks(project_id, owner_agent_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS task_dependencies (
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  blocked_by_task_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id, task_id, blocked_by_task_id)
);
"""


class RelayError(Exception):
    """Base relay error with a stable machine-readable contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "relay_error",
        details: dict[str, Any] | None = None,
        remediation: str | None = None,
        status: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.remediation = remediation
        self.status = status


class RelayDenied(RelayError):
    def __init__(self, message: str, details: dict[str, Any], code: str = "policy_denied"):
        super().__init__(message, code=code, details=details)


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def canonical_resource_id(resource_id: str) -> str:
    value = unicodedata.normalize("NFKC", str(resource_id)).strip()
    if ":" not in value:
        raise RelayError(
            "resource id requires a namespace",
            code="invalid_resource_id",
            details={"resource_id": resource_id},
            remediation="Use <namespace>:<scope>/<name>, for example deploy-slot:project/staging.",
        )
    namespace, target = value.split(":", 1)
    namespace = namespace.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", namespace):
        raise RelayError(
            "invalid resource namespace",
            code="invalid_resource_id",
            details={"resource_id": resource_id, "namespace": namespace},
            remediation="Use a lowercase namespace containing letters, digits, and hyphens.",
        )
    target = target.replace("\\", "/").strip().lower()
    if not target or any(character.isspace() or ord(character) < 32 for character in target):
        raise RelayError(
            "invalid resource target",
            code="invalid_resource_id",
            details={"resource_id": resource_id},
            remediation="Use a non-empty slash-delimited target without whitespace.",
        )
    segments: list[str] = []
    for segment in target.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            raise RelayError(
                "resource target cannot contain parent traversal",
                code="invalid_resource_id",
                details={"resource_id": resource_id},
            )
        segments.append(segment)
    if not segments:
        raise RelayError("invalid resource target", code="invalid_resource_id", details={"resource_id": resource_id})
    return f"{namespace}:{'/'.join(segments)}"


def normalize_handle(handle: str | None) -> str | None:
    if not handle:
        return None
    value = handle.strip().lower()
    if value.startswith("@"):
        value = value[1:]
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_", "."})
    return cleaned or None


def normalize_contact_code(code: str | None) -> str | None:
    if not code:
        return None
    value = code.strip().upper()
    if value.startswith("#"):
        value = value[1:]
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return cleaned or None


def generate_contact_code(conn: sqlite3.Connection, project_id: str) -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        exists = conn.execute(
            "SELECT 1 FROM agents WHERE project_id = ? AND contact_code = ?",
            (project_id, code),
        ).fetchone()
        if not exists:
            return code
    raise RelayError("unable to allocate unique contact code")


def suggested_handles(conn: sqlite3.Connection, project_id: str, handle: str, count: int = 3) -> list[str]:
    suggestions: list[str] = []
    suffix = 2
    while len(suggestions) < count and suffix < 1000:
        suffix_text = f"-{suffix}"
        candidate = f"{handle[: max(1, 48 - len(suffix_text))]}{suffix_text}"
        exists = conn.execute(
            "SELECT 1 FROM agents WHERE project_id = ? AND handle = ?",
            (project_id, candidate),
        ).fetchone()
        if not exists:
            suggestions.append(candidate)
        suffix += 1
    return suggestions


def relay_db(db: str | None = None) -> Path:
    path = Path(db).expanduser() if db else relay_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_relay_db(db: str | None = None) -> None:
    ensure_base_dirs()
    path = relay_db(db)
    cache_key = str(path.resolve())
    with _RELAY_INIT_LOCK:
        if path.exists():
            stat = path.stat()
            if _INITIALIZED_RELAY_DBS.get(cache_key) == (stat.st_dev, stat.st_ino):
                return
        with closing(sqlite3.connect(path, timeout=30)) as conn:
            with conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA busy_timeout=30000")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(RELAY_SCHEMA)
                ensure_agent_columns(conn)
                ensure_message_columns(conn)
                ensure_message_audience(conn)
                ensure_message_receipts(conn)
                ensure_projects(conn)
                normalize_existing_resources(conn)
        stat = path.stat()
        _INITIALIZED_RELAY_DBS[cache_key] = (stat.st_dev, stat.st_ino)


def ensure_agent_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(agents)")}
    if "handle" not in existing:
        conn.execute("ALTER TABLE agents ADD COLUMN handle TEXT")
    if "contact_code" not in existing:
        conn.execute("ALTER TABLE agents ADD COLUMN contact_code TEXT")
    if "user_name" not in existing:
        conn.execute("ALTER TABLE agents ADD COLUMN user_name TEXT")
    if "user_slug" not in existing:
        conn.execute("ALTER TABLE agents ADD COLUMN user_slug TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_handle
          ON agents(project_id, handle)
          WHERE handle IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_contact_code
          ON agents(project_id, contact_code)
          WHERE contact_code IS NOT NULL
        """
    )


def ensure_message_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
    added_audience_policy = "audience_policy" not in existing
    if added_audience_policy:
        conn.execute(
            "ALTER TABLE messages ADD COLUMN audience_policy TEXT NOT NULL DEFAULT 'legacy_registered_at_send'"
        )
    conn.execute(
        """
        UPDATE messages
        SET audience_policy = CASE
          WHEN recipient_agent_id IS NULL THEN 'legacy_registered_at_send'
          ELSE 'direct_recipient'
        END
        WHERE ? OR audience_policy IS NULL OR audience_policy = ''
        """,
        (added_audience_policy,),
    )


def ensure_projects(conn: sqlite3.Connection) -> None:
    project_ids = {
        str(row["project_id"])
        for table in ("agents", "messages", "resources", "leases", "audit_events", "tasks")
        for row in conn.execute(f"SELECT DISTINCT project_id FROM {table} WHERE project_id IS NOT NULL")
        if row["project_id"]
    }
    for project_id in project_ids:
        timestamps = [
            row["value"]
            for row in conn.execute(
                """
                SELECT registered_at AS value FROM agents WHERE project_id = ?
                UNION ALL SELECT created_at FROM messages WHERE project_id = ?
                UNION ALL SELECT created_at FROM audit_events WHERE project_id = ?
                UNION ALL SELECT created_at FROM tasks WHERE project_id = ?
                """,
                (project_id, project_id, project_id, project_id),
            )
            if row["value"]
        ]
        created_at = min(timestamps) if timestamps else utc_now()
        last_activity_at = max(timestamps) if timestamps else created_at
        conn.execute(
            """
            INSERT INTO projects(project_id, display_name, created_at, updated_at, last_activity_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              last_activity_at = CASE
                WHEN excluded.last_activity_at > projects.last_activity_at THEN excluded.last_activity_at
                ELSE projects.last_activity_at
              END
            """,
            (project_id, humanize_project_id(project_id), created_at, last_activity_at, last_activity_at),
        )


def humanize_project_id(project_id: str) -> str:
    words = re.sub(r"[-_]+", " ", project_id).strip()
    return " ".join(word.capitalize() for word in words.split()) or project_id


def ensure_project_record(conn: sqlite3.Connection, project_id: str, timestamp: str | None = None) -> None:
    ts = timestamp or utc_now()
    conn.execute(
        """
        INSERT INTO projects(project_id, display_name, created_at, updated_at, last_activity_at)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
          updated_at = excluded.updated_at,
          last_activity_at = excluded.last_activity_at
        """,
        (project_id, humanize_project_id(project_id), ts, ts, ts),
    )


def ensure_message_receipts(conn: sqlite3.Connection) -> None:
    completed = conn.execute(
        "SELECT 1 FROM relay_meta WHERE key = 'message_receipts_backfill_v2'"
    ).fetchone()
    if completed:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO message_receipts(message_id, agent_id, acked_at)
        SELECT message_id, recipient_agent_id, acked_at
        FROM messages
        WHERE recipient_agent_id IS NOT NULL AND acked_at IS NOT NULL
        """
    )
    uncertain_broadcasts = 0
    broadcasts = list(
        conn.execute(
            "SELECT message_id, project_id, acked_at FROM messages WHERE recipient_agent_id IS NULL AND acked_at IS NOT NULL"
        )
    )
    for message in broadcasts:
        matched_actor = False
        audit_rows = conn.execute(
            """
            SELECT actor_agent_id, payload FROM audit_events
            WHERE project_id = ? AND event_type = 'message.acked' AND actor_agent_id IS NOT NULL
            """,
            (message["project_id"],),
        )
        for audit_row in audit_rows:
            try:
                audit_payload = json.loads(audit_row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if audit_payload.get("message_id") != message["message_id"]:
                continue
            audience = conn.execute(
                "SELECT 1 FROM message_audience WHERE message_id = ? AND agent_id = ?",
                (message["message_id"], audit_row["actor_agent_id"]),
            ).fetchone()
            if audience:
                conn.execute(
                    "INSERT OR IGNORE INTO message_receipts(message_id, agent_id, acked_at) VALUES(?, ?, ?)",
                    (message["message_id"], audit_row["actor_agent_id"], message["acked_at"]),
                )
                matched_actor = True
        if not matched_actor:
            uncertain_broadcasts += 1
    conn.execute(
        "INSERT INTO relay_meta(key, value) VALUES('message_receipts_backfill_v2', ?)",
        (utc_now(),),
    )
    if uncertain_broadcasts:
        conn.execute(
            "INSERT OR REPLACE INTO relay_meta(key, value) VALUES('uncertain_legacy_broadcast_receipts', ?)",
            (str(uncertain_broadcasts),),
        )


def ensure_message_audience(conn: sqlite3.Connection) -> None:
    completed = conn.execute(
        "SELECT 1 FROM relay_meta WHERE key = 'message_audience_backfill_v1'"
    ).fetchone()
    if completed:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO message_audience(message_id, agent_id, delivered_at)
        SELECT message_id, recipient_agent_id, created_at
        FROM messages
        WHERE recipient_agent_id IS NOT NULL
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO message_audience(message_id, agent_id, delivered_at)
        SELECT m.message_id, a.agent_id, m.created_at
        FROM messages AS m
        JOIN agents AS a
          ON a.project_id = m.project_id
         AND a.registered_at <= m.created_at
         AND a.agent_id != COALESCE(m.sender_agent_id, '')
        WHERE m.recipient_agent_id IS NULL
        """
    )
    conn.execute(
        "INSERT INTO relay_meta(key, value) VALUES('message_audience_backfill_v1', ?)",
        (utc_now(),),
    )


def normalize_existing_resources(conn: sqlite3.Connection) -> None:
    rows = list(conn.execute("SELECT project_id, canonical_id, fencing_epoch FROM resources"))
    for row in rows:
        try:
            canonical = canonical_resource_id(row["canonical_id"])
        except RelayError:
            active = conn.execute(
                """
                SELECT lease_id, expires_at FROM leases
                WHERE project_id = ? AND canonical_resource_id = ? AND state = 'active' AND expires_at > ?
                LIMIT 1
                """,
                (row["project_id"], row["canonical_id"], now_ts()),
            ).fetchone()
            if active:
                raise RelayError(
                    "active lease uses a legacy resource id that cannot be normalized",
                    code="resource_migration_conflict",
                    details={
                        "project_id": row["project_id"],
                        "canonical_resource_id": row["canonical_id"],
                        "lease_id": active["lease_id"],
                        "expires_at": active["expires_at"],
                    },
                    remediation="Wait for the legacy lease TTL to expire, then restart the relay and repair the resource id offline.",
                )
            continue
        if canonical == row["canonical_id"]:
            continue
        existing = conn.execute(
            "SELECT fencing_epoch FROM resources WHERE project_id = ? AND canonical_id = ?",
            (row["project_id"], canonical),
        ).fetchone()
        if existing:
            old_active = conn.execute(
                """
                SELECT lease_id, expires_at FROM leases
                WHERE project_id = ? AND canonical_resource_id = ? AND state = 'active' AND expires_at > ?
                LIMIT 1
                """,
                (row["project_id"], row["canonical_id"], now_ts()),
            ).fetchone()
            target_active = conn.execute(
                """
                SELECT lease_id, expires_at FROM leases
                WHERE project_id = ? AND canonical_resource_id = ? AND state = 'active' AND expires_at > ?
                LIMIT 1
                """,
                (row["project_id"], canonical, now_ts()),
            ).fetchone()
            if old_active or (target_active and int(row["fencing_epoch"]) > int(existing["fencing_epoch"])):
                leases = [lease["lease_id"] for lease in (old_active, target_active) if lease]
                expires = [lease["expires_at"] for lease in (old_active, target_active) if lease]
                raise RelayError(
                    "resource normalization would invalidate or merge active leases",
                    code="resource_migration_conflict",
                    details={
                        "project_id": row["project_id"],
                        "legacy_resource_id": row["canonical_id"],
                        "canonical_resource_id": canonical,
                        "active_lease_ids": leases,
                        "latest_expiry": max(expires) if expires else None,
                    },
                    remediation="Wait for the listed lease TTLs to expire before restarting the upgraded relay.",
                )
            epoch = max(int(existing["fencing_epoch"]), int(row["fencing_epoch"]))
            conn.execute(
                "UPDATE resources SET fencing_epoch = ?, updated_at = ? WHERE project_id = ? AND canonical_id = ?",
                (epoch, utc_now(), row["project_id"], canonical),
            )
            conn.execute(
                "UPDATE leases SET canonical_resource_id = ? WHERE project_id = ? AND canonical_resource_id = ?",
                (canonical, row["project_id"], row["canonical_id"]),
            )
            conn.execute(
                "DELETE FROM resources WHERE project_id = ? AND canonical_id = ?",
                (row["project_id"], row["canonical_id"]),
            )
        else:
            conn.execute(
                "UPDATE resources SET canonical_id = ?, updated_at = ? WHERE project_id = ? AND canonical_id = ?",
                (canonical, utc_now(), row["project_id"], row["canonical_id"]),
            )
            conn.execute(
                "UPDATE leases SET canonical_resource_id = ? WHERE project_id = ? AND canonical_resource_id = ?",
                (canonical, row["project_id"], row["canonical_id"]),
            )


@contextmanager
def connect(db: str | None = None) -> Iterator[sqlite3.Connection]:
    init_relay_db(db)
    conn = sqlite3.connect(relay_db(db), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def audit(
    conn: sqlite3.Connection,
    event_type: str,
    payload: dict[str, Any],
    project_id: str | None = None,
    actor_agent_id: str | None = None,
    resource_id: str | None = None,
) -> None:
    created_at = utc_now()
    if project_id:
        ensure_project_record(conn, project_id, created_at)
    conn.execute(
        """
        INSERT INTO audit_events(project_id, event_type, actor_agent_id, resource_id, payload, created_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (project_id, event_type, actor_agent_id, resource_id, json_dumps(payload), created_at),
    )


def register_agent(payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    agent_id = payload.get("agent_id") or make_id("agent")
    runtime = payload.get("runtime") or "custom"
    requested_handle = normalize_handle(payload.get("handle"))
    requested_code = normalize_contact_code(payload.get("contact_code"))
    ts = utc_now()
    with connect(db) as conn, transaction(conn):
        existing = conn.execute(
            """
            SELECT registered_at, handle, contact_code, name, user_name, user_slug
              FROM agents
             WHERE project_id = ? AND agent_id = ?
            """,
            (project_id, agent_id),
        ).fetchone()
        supplied_user_name = payload.get("user_name")
        existing_user_name = existing["user_name"] if existing else None
        existing_user_slug = existing["user_slug"] if existing else None
        profile = None
        if supplied_user_name:
            try:
                profile = profile_from_name(str(supplied_user_name), "relay-request")
            except IdentityError as exc:
                raise RelayError(
                    str(exc),
                    code=exc.code,
                    details=exc.details,
                    remediation=exc.remediation,
                ) from exc
            if existing_user_slug and profile["slug"] != existing_user_slug:
                raise RelayError(
                    "Agent is already attributed to a different Commons user",
                    code="agent_user_identity_conflict",
                    details={
                        "project_id": project_id,
                        "agent_id": agent_id,
                        "existing_user_slug": existing_user_slug,
                        "requested_user_slug": profile["slug"],
                    },
                    remediation="Register a new Agent id instead of changing the human owner of an existing Agent.",
                )
        elif existing_user_name and existing_user_slug:
            profile = {
                "configured": True,
                "name": existing_user_name,
                "slug": existing_user_slug,
                "source": "relay-record",
            }
        elif not existing and user_prefix_enforcement_enabled():
            raise RelayError(
                "Commons user name is required for new Agent registration",
                code="user_name_required",
                remediation=(
                    'Ask the user for their name, run commons user set --name "<name>", '
                    "then register the Agent again."
                ),
            )

        handle = requested_handle or (existing["handle"] if existing else None)
        if profile:
            if not handle:
                raise RelayError(
                    "A user-prefixed Agent handle is required",
                    code="agent_handle_required",
                    details={"required_prefix": f"{profile['slug']}-"},
                    remediation="Register with --handle <user-name>-<agent-name>.",
                )
            if len(handle) > MAX_AGENT_HANDLE_LENGTH:
                raise RelayError(
                    "Agent handle is too long",
                    code="invalid_agent_handle",
                    details={"maximum_length": MAX_AGENT_HANDLE_LENGTH},
                    remediation=f"Use a handle no longer than {MAX_AGENT_HANDLE_LENGTH} characters.",
                )
            if not handle_has_user_prefix(handle, str(profile["slug"])):
                raise RelayError(
                    "Agent handle must begin with the Commons user prefix",
                    code="agent_handle_user_prefix_required",
                    details={
                        "handle": handle,
                        "required_prefix": f"{profile['slug']}-",
                    },
                    remediation=(
                        'Run commons user set --name "<name>" locally and let the Commons CLI '
                        "generate the prefixed handle."
                    ),
                )
            user_name = str(profile["name"])
            user_slug = str(profile["slug"])
            proposed_name = payload.get("name") or (existing["name"] if existing else None) or handle
            name = qualify_name(profile, proposed_name)
        else:
            # Legacy Agents remain addressable until they naturally re-register
            # through a client that supplies human attribution.
            user_name = None
            user_slug = None
            name = payload.get("name") or (existing["name"] if existing else None)
        if handle:
            handle_owner = conn.execute(
                "SELECT agent_id FROM agents WHERE project_id = ? AND handle = ? AND agent_id != ?",
                (project_id, handle, agent_id),
            ).fetchone()
            if handle_owner:
                raise RelayDenied(
                    "agent handle already in use",
                    {
                        "project_id": project_id,
                        "handle": handle,
                        "agent_id": handle_owner["agent_id"],
                        "suggested_handles": suggested_handles(conn, project_id, handle),
                    },
                    code="agent_handle_conflict",
                )
        if requested_code:
            code_owner = conn.execute(
                "SELECT agent_id FROM agents WHERE project_id = ? AND contact_code = ? AND agent_id != ?",
                (project_id, requested_code, agent_id),
            ).fetchone()
            if code_owner:
                raise RelayDenied(
                    "agent contact code already in use",
                    {"project_id": project_id, "contact_code": requested_code, "agent_id": code_owner["agent_id"]},
                )
        registered_at = existing["registered_at"] if existing else ts
        contact_code = requested_code or (existing["contact_code"] if existing else None) or generate_contact_code(conn, project_id)
        conn.execute(
            """
            INSERT INTO agents(
              project_id, agent_id, handle, contact_code, name, user_name, user_slug,
              runtime, workspace, task_id, status, registered_at, heartbeat_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'online', ?, ?)
            ON CONFLICT(project_id, agent_id) DO UPDATE SET
              handle = excluded.handle,
              contact_code = excluded.contact_code,
              name = excluded.name,
              user_name = excluded.user_name,
              user_slug = excluded.user_slug,
              runtime = excluded.runtime,
              workspace = excluded.workspace,
              task_id = excluded.task_id,
              status = 'online',
              heartbeat_at = excluded.heartbeat_at
            """,
            (
                project_id,
                agent_id,
                handle,
                contact_code,
                name,
                user_name,
                user_slug,
                runtime,
                payload.get("workspace"),
                payload.get("task_id"),
                registered_at,
                ts,
            ),
        )
        audit(
            conn,
            "agent.registered",
            {
                "agent_id": agent_id,
                "runtime": runtime,
                "handle": handle,
                "contact_code": contact_code,
                "user_name": user_name,
                "user_slug": user_slug,
            },
            project_id,
            agent_id,
        )
        row = conn.execute(
            "SELECT * FROM agents WHERE project_id = ? AND agent_id = ?",
            (project_id, agent_id),
        ).fetchone()
    return row_to_dict(row)


def list_agents(project_id: str, db: str | None = None) -> list[dict[str, Any]]:
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT * FROM agents WHERE project_id = ? ORDER BY heartbeat_at DESC",
            (project_id,),
        )
        return [agent_with_presence(row) for row in rows]


def agent_with_presence(row: sqlite3.Row) -> dict[str, Any]:
    item = row_to_dict(row)
    try:
        heartbeat = datetime.fromisoformat(str(row["heartbeat_at"]).replace("Z", "+00:00"))
        age_seconds = max(0, int((datetime.now(timezone.utc) - heartbeat).total_seconds()))
    except (TypeError, ValueError):
        age_seconds = 10**9
    if row["status"] == "offline" or age_seconds > AGENT_ACTIVE_SECONDS:
        presence = "offline"
    elif row["status"] == "idle" or age_seconds > AGENT_RECENT_SECONDS:
        presence = "idle"
    else:
        presence = "online"
    item["presence"] = presence
    item["active"] = presence != "offline"
    item["last_seen_at"] = row["heartbeat_at"]
    item["last_seen_seconds"] = age_seconds
    return item


def touch_agent(conn: sqlite3.Connection, project_id: str, agent_id: str | None) -> None:
    if agent_id:
        conn.execute(
            """
            UPDATE agents
            SET heartbeat_at = ?, status = CASE WHEN status = 'offline' THEN 'online' ELSE status END
            WHERE project_id = ? AND agent_id = ?
            """,
            (utc_now(), project_id, agent_id),
        )


def heartbeat_agent(payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    agent_id = required(payload, "agent_id")
    status = str(payload.get("status") or "online")
    if status not in {"online", "busy", "idle", "offline"}:
        raise RelayError("invalid agent status", code="invalid_agent_status")
    with connect(db) as conn, transaction(conn):
        row = conn.execute(
            "SELECT * FROM agents WHERE project_id = ? AND agent_id = ?",
            (project_id, agent_id),
        ).fetchone()
        if not row:
            raise RelayError(f"unknown agent: {agent_id}", code="agent_not_found")
        conn.execute(
            "UPDATE agents SET heartbeat_at = ?, status = ? WHERE project_id = ? AND agent_id = ?",
            (utc_now(), status, project_id, agent_id),
        )
        if row["status"] != status:
            audit(
                conn,
                "agent.status_changed",
                {"agent_id": agent_id, "from": row["status"], "to": status},
                project_id,
                agent_id,
            )
        updated = conn.execute(
            "SELECT * FROM agents WHERE project_id = ? AND agent_id = ?",
            (project_id, agent_id),
        ).fetchone()
    return agent_with_presence(updated)


def send_message(payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    body = required(payload, "body")
    sender_agent_id = required(payload, "sender_agent_id")
    recipient_agent_id = payload.get("recipient_agent_id")
    message_id = make_id("msg")
    thread_id = payload.get("thread_id") or make_id("thread")
    message_type = payload.get("message_type") or "note"
    ts = utc_now()
    with connect(db) as conn, transaction(conn):
        sender = conn.execute(
            "SELECT 1 FROM agents WHERE project_id = ? AND agent_id = ?",
            (project_id, sender_agent_id),
        ).fetchone()
        if not sender:
            raise RelayError(f"unknown agent: {sender_agent_id}", code="agent_not_found")
        touch_agent(conn, project_id, sender_agent_id)
        recipient_ref = payload.get("recipient")
        if recipient_ref is not None:
            recipient_agent_id = resolve_recipient(conn, project_id, str(recipient_ref))
        elif recipient_agent_id:
            recipient_agent_id = resolve_recipient(conn, project_id, str(recipient_agent_id))
        audience_policy = "direct_recipient" if recipient_agent_id is not None else "active_agents_at_send"
        conn.execute(
            """
            INSERT INTO messages(
              message_id, project_id, thread_id, sender_agent_id, recipient_agent_id,
              message_type, audience_policy, body, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                project_id,
                thread_id,
                sender_agent_id,
                recipient_agent_id,
                message_type,
                audience_policy,
                body,
                ts,
            ),
        )
        if recipient_agent_id is not None:
            conn.execute(
                "INSERT INTO message_audience(message_id, agent_id, delivered_at) VALUES(?, ?, ?)",
                (message_id, recipient_agent_id, ts),
            )
        else:
            conn.execute(
                """
                INSERT INTO message_audience(message_id, agent_id, delivered_at)
                SELECT ?, agent_id, ? FROM agents
                WHERE project_id = ?
                  AND agent_id != COALESCE(?, '')
                  AND status != 'offline'
                  AND heartbeat_at >= ?
                """,
                (message_id, ts, project_id, sender_agent_id, active_agent_cutoff()),
            )
        audit(
            conn,
            "message.sent",
            {
                "message_id": message_id,
                "thread_id": thread_id,
                "recipient_agent_id": recipient_agent_id,
            },
            project_id,
            sender_agent_id,
        )
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
    return row_to_dict(row)


def resolve_recipient(conn: sqlite3.Connection, project_id: str, recipient: str) -> str | None:
    value = recipient.strip()
    if not value or value in {"*", "broadcast", "@broadcast", "#broadcast"}:
        return None
    handle = normalize_handle(value)
    code = normalize_contact_code(value)
    row = conn.execute(
        """
        SELECT agent_id FROM agents
        WHERE project_id = ? AND (agent_id = ? OR handle = ? OR contact_code = ?)
        """,
        (project_id, value, handle, code),
    ).fetchone()
    if not row:
        raise RelayError(f"unknown message recipient: {recipient}")
    return row["agent_id"]


def fetch_inbox(
    project_id: str,
    agent_id: str,
    unread_only: bool = False,
    limit: int = 50,
    cursor: str | None = None,
    before_message_id: str | None = None,
    db: str | None = None,
) -> dict[str, Any]:
    requested_limit = max(1, int(limit))
    server_limit = 200
    effective_limit = min(requested_limit, server_limit)
    if cursor and before_message_id:
        raise RelayError(
            "cursor and before cannot be used together",
            code="invalid_pagination",
            remediation="Use either --cursor or --before, not both.",
        )
    query = """
        SELECT m.rowid AS message_sequence, m.*, r.acked_at AS receipt_acked_at
        FROM messages AS m
        JOIN message_audience AS audience
          ON audience.message_id = m.message_id AND audience.agent_id = ?
        LEFT JOIN message_receipts AS r
          ON r.message_id = m.message_id AND r.agent_id = ?
        WHERE m.project_id = ?
    """
    params: list[Any] = [agent_id, agent_id, project_id]
    if unread_only:
        query += """
          AND CASE
            WHEN m.recipient_agent_id IS NULL THEN r.acked_at IS NULL
            ELSE COALESCE(r.acked_at, m.acked_at) IS NULL
          END
        """
    with connect(db) as conn:
        sequence_anchor: int | None = None
        legacy_anchor: tuple[str, str] | None = None
        if cursor:
            decoded = decode_inbox_cursor(cursor)
            if isinstance(decoded, int):
                sequence_anchor = decoded
            else:
                legacy_anchor = decoded
        elif before_message_id:
            row = conn.execute(
                """
                SELECT m.rowid AS message_sequence FROM messages AS m
                JOIN message_audience AS audience
                  ON audience.message_id = m.message_id AND audience.agent_id = ?
                WHERE m.project_id = ? AND m.message_id = ?
                """,
                (agent_id, project_id, before_message_id),
            ).fetchone()
            if not row:
                raise RelayError(
                    f"unknown inbox message: {before_message_id}",
                    code="message_not_found",
                )
            sequence_anchor = int(row["message_sequence"])
        if sequence_anchor is not None:
            query += " AND m.rowid < ?"
            params.append(sequence_anchor)
        elif legacy_anchor:
            query += " AND (m.created_at < ? OR (m.created_at = ? AND m.message_id < ?))"
            params.extend([legacy_anchor[0], legacy_anchor[0], legacy_anchor[1]])
        query += " ORDER BY m.rowid DESC LIMIT ?"
        params.append(effective_limit + 1)
        rows = list(conn.execute(query, params))

    has_more = len(rows) > effective_limit
    rows = rows[:effective_limit]
    messages: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        receipt_acked_at = item.pop("receipt_acked_at")
        if item["recipient_agent_id"] is None:
            item["acked_at"] = receipt_acked_at
        else:
            item["acked_at"] = receipt_acked_at or item.get("acked_at")
        item["acknowledged_by_agent"] = item["acked_at"] is not None
        messages.append(item)
    next_cursor = None
    if has_more and messages:
        last = messages[-1]
        next_cursor = encode_inbox_cursor(int(last["message_sequence"]))
    return {
        "messages": messages,
        "page": {
            "requested_limit": requested_limit,
            "effective_limit": effective_limit,
            "server_limit": server_limit,
            "returned_count": len(messages),
            "has_more": has_more,
            "window_complete": not has_more,
            "truncated": requested_limit > server_limit and has_more,
            "next_cursor": next_cursor,
        },
    }


def encode_inbox_cursor(message_sequence: int) -> str:
    raw = json.dumps({"v": 1, "before_sequence": message_sequence}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_inbox_cursor(cursor: str) -> int | tuple[str, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise RelayError(
            "invalid inbox cursor",
            code="invalid_cursor",
            remediation="Use the next_cursor returned by the previous inbox response.",
        ) from exc
    if isinstance(value, dict) and value.get("v") == 1 and isinstance(value.get("before_sequence"), int):
        if value["before_sequence"] > 0:
            return value["before_sequence"]
    if isinstance(value, list) and len(value) == 2 and all(isinstance(item, str) and item for item in value):
        return value[0], value[1]
    raise RelayError(
        "invalid inbox cursor",
        code="invalid_cursor",
        remediation="Use the next_cursor returned by the previous inbox response.",
    )


def get_message(project_id: str, message_id: str, agent_id: str, db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE project_id = ? AND message_id = ?",
            (project_id, message_id),
        ).fetchone()
        if not row:
            raise RelayError(f"unknown message: {message_id}", code="message_not_found")
        if row["recipient_agent_id"] is not None and agent_id not in {
            row["recipient_agent_id"],
            row["sender_agent_id"],
        }:
            raise RelayDenied(
                "message access denied",
                {"message_id": message_id, "agent_id": agent_id},
                code="message_access_denied",
            )
        if row["recipient_agent_id"] is None and agent_id != row["sender_agent_id"]:
            audience = conn.execute(
                "SELECT 1 FROM message_audience WHERE message_id = ? AND agent_id = ?",
                (message_id, agent_id),
            ).fetchone()
            if not audience:
                raise RelayDenied(
                    "message access denied",
                    {"message_id": message_id, "agent_id": agent_id},
                    code="message_access_denied",
                )
        receipts = [
            row_to_dict(receipt)
            for receipt in conn.execute(
                "SELECT agent_id, acked_at FROM message_receipts WHERE message_id = ? ORDER BY acked_at",
                (message_id,),
            )
        ]
        eligible_count = 1
        if row["recipient_agent_id"] is None:
            eligible_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM message_audience WHERE message_id = ?",
                    (message_id,),
                ).fetchone()[0]
            )
        result = row_to_dict(row)
        result["receipts"] = receipts
        result["receipt_summary"] = {
            "acked_count": len(receipts),
            "eligible_agent_count": eligible_count,
            "all_acked": eligible_count > 0 and len(receipts) >= eligible_count,
            "audience_policy": row["audience_policy"],
        }
        return result


def active_agent_cutoff() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=AGENT_ACTIVE_SECONDS)
    return cutoff.isoformat(timespec="seconds").replace("+00:00", "Z")


def ack_message(
    message_id: str,
    agent_id: str | None = None,
    db: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    ts = utc_now()
    with connect(db) as conn, transaction(conn):
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if not row:
            raise RelayError(f"unknown message: {message_id}")
        if project_id and row["project_id"] != project_id:
            raise RelayError(f"unknown message: {message_id}")
        if not agent_id:
            raise RelayError(
                "agent_id is required to acknowledge a message",
                code="ack_agent_required",
                remediation="Pass --agent <agent_id> so broadcast receipts remain per-agent.",
            )
        audience = conn.execute(
            "SELECT 1 FROM message_audience WHERE message_id = ? AND agent_id = ?",
            (message_id, agent_id),
        ).fetchone()
        if not audience:
            raise RelayDenied("message recipient mismatch", {"message_id": message_id}, code="message_recipient_mismatch")
        if row["recipient_agent_id"] and row["recipient_agent_id"] != agent_id:
            raise RelayDenied("message recipient mismatch", {"message_id": message_id})
        inserted = conn.execute(
            "INSERT OR IGNORE INTO message_receipts(message_id, agent_id, acked_at) VALUES(?, ?, ?)",
            (message_id, agent_id, ts),
        ).rowcount
        receipt = conn.execute(
            "SELECT acked_at FROM message_receipts WHERE message_id = ? AND agent_id = ?",
            (message_id, agent_id),
        ).fetchone()
        if row["recipient_agent_id"] is not None:
            conn.execute("UPDATE messages SET acked_at = COALESCE(acked_at, ?) WHERE message_id = ?", (ts, message_id))
        touch_agent(conn, row["project_id"], agent_id)
        if inserted:
            audit(conn, "message.acked", {"message_id": message_id}, row["project_id"], agent_id)
    return {
        "ok": True,
        "message_id": message_id,
        "agent_id": agent_id,
        "acked_at": receipt["acked_at"],
        "newly_acked": bool(inserted),
    }


def ensure_resource(conn: sqlite3.Connection, project_id: str, resource_id: str) -> sqlite3.Row:
    canonical = canonical_resource_id(resource_id)
    row = conn.execute(
        "SELECT * FROM resources WHERE project_id = ? AND canonical_id = ?",
        (project_id, canonical),
    ).fetchone()
    if row:
        return row
    ts = utc_now()
    conn.execute(
        """
        INSERT INTO resources(project_id, canonical_id, fencing_epoch, created_at, updated_at)
        VALUES(?, ?, 0, ?, ?)
        """,
        (project_id, canonical, ts, ts),
    )
    return conn.execute(
        "SELECT * FROM resources WHERE project_id = ? AND canonical_id = ?",
        (project_id, canonical),
    ).fetchone()


def expire_leases(conn: sqlite3.Connection, project_id: str, canonical: str) -> None:
    now = now_ts()
    rows = list(
        conn.execute(
            """
            SELECT * FROM leases
            WHERE project_id = ? AND canonical_resource_id = ? AND state = 'active' AND expires_at <= ?
            """,
            (project_id, canonical, now),
        )
    )
    for row in rows:
        conn.execute("UPDATE leases SET state = 'expired' WHERE lease_id = ?", (row["lease_id"],))
        audit(
            conn,
            "lease.expired",
            {"lease_id": row["lease_id"], "resource_id": row["resource_id"]},
            project_id,
            row["holder_agent_id"],
            row["resource_id"],
        )


def expire_project_leases(conn: sqlite3.Connection, project_id: str) -> None:
    now = now_ts()
    rows = list(
        conn.execute(
            """
            SELECT * FROM leases
            WHERE project_id = ? AND state = 'active' AND expires_at <= ?
            """,
            (project_id, now),
        )
    )
    for row in rows:
        conn.execute("UPDATE leases SET state = 'expired' WHERE lease_id = ?", (row["lease_id"],))
        audit(
            conn,
            "lease.expired",
            {"lease_id": row["lease_id"], "resource_id": row["resource_id"]},
            project_id,
            row["holder_agent_id"],
            row["resource_id"],
        )


def lease_conflicts(existing_mode: str, requested_mode: str) -> bool:
    return existing_mode not in LEASE_COMPAT.get(requested_mode, set())


def lease_ttl_seconds(payload: dict[str, Any]) -> int:
    try:
        ttl_seconds = int(payload.get("ttl_seconds") or seconds_from_ttl(payload.get("ttl")))
    except (TypeError, ValueError) as exc:
        raise RelayError(
            f"invalid lease ttl: {payload.get('ttl') or payload.get('ttl_seconds')}",
            code="invalid_lease_ttl",
        ) from exc
    if ttl_seconds <= 0:
        raise RelayError("lease ttl must be greater than zero", code="invalid_lease_ttl")
    return ttl_seconds


def acquire_lease(payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    resource_id = required(payload, "resource_id")
    mode = payload.get("mode") or "write"
    if mode not in LEASE_COMPAT:
        raise RelayError(f"invalid lease mode: {mode}")
    ttl_seconds = lease_ttl_seconds(payload)
    holder = required(payload, "holder_agent_id")
    with connect(db) as conn, transaction(conn):
        registered = conn.execute(
            "SELECT 1 FROM agents WHERE project_id = ? AND agent_id = ?",
            (project_id, holder),
        ).fetchone()
        if not registered:
            raise RelayError(f"unknown agent: {holder}", code="agent_not_found")
        touch_agent(conn, project_id, holder)
        resource = ensure_resource(conn, project_id, resource_id)
        canonical = resource["canonical_id"]
        expire_leases(conn, project_id, canonical)
        active = list(
            conn.execute(
                """
                SELECT * FROM leases
                WHERE project_id = ? AND canonical_resource_id = ? AND state = 'active'
                ORDER BY acquired_at
                """,
                (project_id, canonical),
            )
        )
        conflicts = [row for row in active if lease_conflicts(row["mode"], mode)]
        if conflicts:
            conflict = row_to_dict(conflicts[0])
            holder_agent = conn.execute(
                "SELECT handle, contact_code FROM agents WHERE project_id = ? AND agent_id = ?",
                (project_id, conflict["holder_agent_id"]),
            ).fetchone()
            holder_handle = holder_agent["handle"] if holder_agent else None
            holder_contact_code = holder_agent["contact_code"] if holder_agent else None
            coordination_recipient = f"@{holder_handle}" if holder_handle else conflict["holder_agent_id"]
            details = {
                "project_id": project_id,
                "resource_id": resource_id,
                "mode": mode,
                "holder_agent_id": conflict["holder_agent_id"],
                "holder_handle": holder_handle,
                "holder_contact_code": holder_contact_code,
                "holder_lease_id": conflict["lease_id"],
                "holder_mode": conflict["mode"],
                "holder_fencing_epoch": conflict["fencing_epoch"],
                "expires_at": conflict["expires_at"],
                "coordination_recipient": coordination_recipient,
                "safe_next_actions": [
                    shlex.join(
                        [
                            "commons",
                            "remote",
                            "msg",
                            "send",
                            coordination_recipient,
                            f"Can you release {resource_id} when done?",
                            "--remote",
                            "default",
                            "--project",
                            project_id,
                            "--sender",
                            holder,
                        ]
                    ),
                    shlex.join(
                        [
                            "commons",
                            "remote",
                            "lease",
                            "list",
                            "--remote",
                            "default",
                            "--project",
                            project_id,
                            "--active",
                        ]
                    ),
                ],
            }
            if conflict["holder_agent_id"] == holder:
                details["same_holder"] = True
                details["safe_next_actions"] = [
                    shlex.join(
                        [
                            "commons",
                            "remote",
                            "lease",
                            "renew",
                            conflict["lease_id"],
                            "--remote",
                            "default",
                            "--project",
                            project_id,
                            "--ttl",
                            str(payload.get("ttl") or "30m"),
                            "--agent",
                            holder,
                            "--fencing-epoch",
                            str(conflict["fencing_epoch"]),
                        ]
                    ),
                    details["safe_next_actions"][1],
                ]
            audit(conn, "lease.denied", details, project_id, holder, resource_id)
            if details.get("same_holder"):
                raise RelayDenied("lease already held by requesting agent", details, code="lease_already_held")
            raise RelayDenied("lease conflict", details, code="lease_conflict")
        epoch = int(resource["fencing_epoch"])
        if mode in FENCED_LEASE_MODES:
            epoch += 1
            conn.execute(
                "UPDATE resources SET fencing_epoch = ?, updated_at = ? WHERE project_id = ? AND canonical_id = ?",
                (epoch, utc_now(), project_id, canonical),
            )
        lease_id = make_id("lease")
        acquired_at = utc_now()
        expires_at = now_ts() + ttl_seconds
        conn.execute(
            """
            INSERT INTO leases(lease_id, project_id, resource_id, canonical_resource_id, mode, holder_agent_id, reason, state, fencing_epoch, acquired_at, expires_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                lease_id,
                project_id,
                resource_id,
                canonical,
                mode,
                holder,
                payload.get("reason"),
                epoch,
                acquired_at,
                expires_at,
            ),
        )
        audit(
            conn,
            "lease.granted",
            {"lease_id": lease_id, "resource_id": resource_id, "mode": mode, "fencing_epoch": epoch},
            project_id,
            holder,
            resource_id,
        )
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    return row_to_dict(row)


def list_leases(project_id: str, active_only: bool = False, db: str | None = None) -> list[dict[str, Any]]:
    with connect(db) as conn:
        if active_only:
            with transaction(conn):
                expire_project_leases(conn, project_id)
        if active_only:
            rows = conn.execute(
                "SELECT * FROM leases WHERE project_id = ? AND state = 'active' ORDER BY acquired_at DESC",
                (project_id,),
            )
        else:
            rows = conn.execute(
                "SELECT * FROM leases WHERE project_id = ? ORDER BY acquired_at DESC",
                (project_id,),
            )
        return [row_to_dict(row) for row in rows]


def renew_lease(
    lease_id: str,
    payload: dict[str, Any],
    db: str | None = None,
) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    holder_agent_id = required(payload, "holder_agent_id")
    fencing_epoch = payload.get("fencing_epoch")
    if fencing_epoch is None:
        raise RelayError(
            "fencing_epoch is required to renew a lease",
            code="fencing_epoch_required",
            details={"lease_id": lease_id, "operation": "renew"},
            remediation="List active leases and retry with the exact fencing_epoch for this lease.",
        )
    ttl_seconds = lease_ttl_seconds(payload)
    with connect(db) as conn, transaction(conn):
        row = conn.execute(
            "SELECT * FROM leases WHERE project_id = ? AND lease_id = ?",
            (project_id, lease_id),
        ).fetchone()
        if not row:
            raise RelayError(f"unknown lease: {lease_id}")
        if not row["holder_agent_id"] or holder_agent_id != row["holder_agent_id"]:
            raise RelayDenied("lease holder mismatch", {"lease_id": lease_id})
        if int(fencing_epoch) != int(row["fencing_epoch"]):
            raise RelayDenied(
                "stale fencing epoch",
                {"lease_id": lease_id, "expected_fencing_epoch": row["fencing_epoch"]},
                code="stale_fencing_epoch",
            )
        expire_leases(conn, project_id, row["canonical_resource_id"])
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if row["state"] != "active":
            raise RelayDenied(
                "cannot renew inactive lease",
                {"lease_id": lease_id, "state": row["state"]},
                code="inactive_lease",
            )
        previous_expires_at = float(row["expires_at"])
        expires_at = now_ts() + ttl_seconds
        touch_agent(conn, project_id, holder_agent_id)
        conn.execute(
            "UPDATE leases SET expires_at = ? WHERE lease_id = ? AND state = 'active'",
            (expires_at, lease_id),
        )
        audit(
            conn,
            "lease.renewed",
            {
                "lease_id": lease_id,
                "resource_id": row["resource_id"],
                "fencing_epoch": row["fencing_epoch"],
                "previous_expires_at": previous_expires_at,
                "expires_at": expires_at,
                "ttl_seconds": ttl_seconds,
            },
            project_id,
            holder_agent_id,
            row["resource_id"],
        )
        updated = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    result = row_to_dict(updated)
    result.update(
        {
            "ok": True,
            "previous_expires_at": previous_expires_at,
            "ttl_seconds": ttl_seconds,
        }
    )
    return result


def release_lease(
    lease_id: str,
    holder_agent_id: str | None = None,
    db: str | None = None,
    project_id: str | None = None,
    fencing_epoch: int | None = None,
) -> dict[str, Any]:
    with connect(db) as conn, transaction(conn):
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not row:
            raise RelayError(f"unknown lease: {lease_id}")
        if project_id and row["project_id"] != project_id:
            raise RelayError(f"unknown lease: {lease_id}")
        if not holder_agent_id:
            raise RelayError("holder_agent_id is required", code="lease_holder_required")
        if not row["holder_agent_id"] or holder_agent_id != row["holder_agent_id"]:
            raise RelayDenied("lease holder mismatch", {"lease_id": lease_id})
        if fencing_epoch is None:
            raise RelayError(
                "fencing_epoch is required to release a lease",
                code="fencing_epoch_required",
                details={"lease_id": lease_id, "operation": "release"},
                remediation="List active leases and retry with the exact fencing_epoch for this lease.",
            )
        if int(fencing_epoch) != int(row["fencing_epoch"]):
            raise RelayDenied(
                "stale fencing epoch",
                {"lease_id": lease_id, "expected_fencing_epoch": row["fencing_epoch"]},
                code="stale_fencing_epoch",
            )
        if row["state"] == "released":
            return {"ok": True, "lease_id": lease_id, "state": "released", "newly_released": False}
        if row["state"] != "active":
            raise RelayDenied(
                "cannot release inactive lease",
                {"lease_id": lease_id, "state": row["state"]},
                code="inactive_lease",
            )
        touch_agent(conn, row["project_id"], holder_agent_id)
        conn.execute(
            "UPDATE leases SET state = 'released', released_at = ? WHERE lease_id = ? AND state = 'active'",
            (utc_now(), lease_id),
        )
        audit(
            conn,
            "lease.released",
            {"lease_id": lease_id, "resource_id": row["resource_id"]},
            row["project_id"],
            holder_agent_id,
            row["resource_id"],
        )
    return {"ok": True, "lease_id": lease_id, "state": "released", "newly_released": True}


def audit_recent(project_id: str, limit: int = 50, db: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE project_id = ? ORDER BY event_id DESC LIMIT ?",
            (project_id, limit),
        )
        return [row_to_dict(row) for row in rows]


def relay_status(project_id: str, db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        agents = int(conn.execute("SELECT COUNT(*) FROM agents WHERE project_id = ?", (project_id,)).fetchone()[0])
        active_leases = int(
            conn.execute(
                "SELECT COUNT(*) FROM leases WHERE project_id = ? AND state = 'active' AND expires_at > ?",
                (project_id, now_ts()),
            ).fetchone()[0]
        )
    return {
        "ok": True,
        "service": "commons-relay",
        "protocol_version": 1,
        "project_id": project_id,
        "agents": agents,
        "active_leases": active_leases,
        "features": {
            "inbox_envelope": True,
            "message_audience": True,
            "message_receipts": True,
            "sequence_cursor": True,
            "fenced_release": True,
            "fenced_renewal": True,
            "remote_tasks": True,
            "console": True,
        },
        "security_model": {
            "authentication": "shared_bearer_token",
            "actor_bound": False,
            "project_authorization": "trusted_team_namespace",
            "trust_boundary": "single_trusted_team",
        },
    }


def validate_remote_task_status(value: Any) -> str:
    status = str(value or "created")
    if status not in REMOTE_TASK_STATUSES:
        raise RelayError(
            f"invalid task status: {status}",
            code="invalid_task_status",
            details={"allowed": sorted(REMOTE_TASK_STATUSES)},
        )
    return status


def validate_progress_percent(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        progress = int(value)
    except (TypeError, ValueError) as exc:
        raise RelayError("progress_percent must be an integer", code="invalid_task_progress") from exc
    if progress < 0 or progress > 100:
        raise RelayError("progress_percent must be between 0 and 100", code="invalid_task_progress")
    return progress


def assert_project_agent(conn: sqlite3.Connection, project_id: str, agent_id: str | None) -> None:
    if not agent_id:
        return
    exists = conn.execute(
        "SELECT 1 FROM agents WHERE project_id = ? AND agent_id = ?",
        (project_id, agent_id),
    ).fetchone()
    if not exists:
        raise RelayError(f"unknown agent: {agent_id}", code="agent_not_found")


def replace_task_dependencies(
    conn: sqlite3.Connection,
    project_id: str,
    task_id: str,
    blocked_by: list[Any],
) -> None:
    normalized = [str(value) for value in blocked_by if value]
    if task_id in normalized:
        raise RelayError("a task cannot block itself", code="task_dependency_cycle")
    for dependency_id in normalized:
        exists = conn.execute(
            "SELECT 1 FROM tasks WHERE project_id = ? AND task_id = ?",
            (project_id, dependency_id),
        ).fetchone()
        if not exists:
            raise RelayError(f"unknown blocking task: {dependency_id}", code="task_not_found")
    conn.execute("DELETE FROM task_dependencies WHERE project_id = ? AND task_id = ?", (project_id, task_id))
    for dependency_id in dict.fromkeys(normalized):
        conn.execute(
            """
            INSERT INTO task_dependencies(project_id, task_id, blocked_by_task_id, created_at)
            VALUES(?, ?, ?, ?)
            """,
            (project_id, task_id, dependency_id, utc_now()),
        )


def remote_tasks_to_dict(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    if not rows:
        return []
    project_id = str(rows[0]["project_id"])
    if any(str(row["project_id"]) != project_id for row in rows):
        raise RelayError("task rows must belong to one project", code="project_mismatch")

    owner_ids = sorted({str(row["owner_agent_id"]) for row in rows if row["owner_agent_id"]})
    owners: dict[str, dict[str, Any]] = {}
    if owner_ids:
        owner_rows = conn.execute(
            """
            SELECT agent_id, handle, contact_code, runtime, status, heartbeat_at
            FROM agents
            WHERE project_id = ?
            """,
            (project_id,),
        )
        owner_id_set = set(owner_ids)
        owners = {
            str(owner["agent_id"]): agent_with_presence(owner)
            for owner in owner_rows
            if str(owner["agent_id"]) in owner_id_set
        }

    task_ids = [str(row["task_id"]) for row in rows]
    task_id_set = set(task_ids)
    dependencies: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    for dependency in conn.execute(
        """
        SELECT task_id, blocked_by_task_id
        FROM task_dependencies
        WHERE project_id = ?
        ORDER BY task_id, blocked_by_task_id
        """,
        (project_id,),
    ):
        task_id = str(dependency["task_id"])
        if task_id in task_id_set:
            dependencies[task_id].append(str(dependency["blocked_by_task_id"]))

    tasks = []
    for row in rows:
        task = row_to_dict(row)
        owner_agent_id = str(row["owner_agent_id"]) if row["owner_agent_id"] else ""
        task["owner"] = owners.get(owner_agent_id)
        task["blocked_by"] = dependencies[str(row["task_id"])]
        tasks.append(task)
    return tasks


def remote_task_to_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    task = row_to_dict(row)
    owner = None
    if row["owner_agent_id"]:
        owner_row = conn.execute(
            "SELECT agent_id, handle, contact_code, runtime, status, heartbeat_at FROM agents WHERE project_id = ? AND agent_id = ?",
            (row["project_id"], row["owner_agent_id"]),
        ).fetchone()
        if owner_row:
            owner = agent_with_presence(owner_row)
    task["owner"] = owner
    task["blocked_by"] = [
        dependency["blocked_by_task_id"]
        for dependency in conn.execute(
            """
            SELECT blocked_by_task_id FROM task_dependencies
            WHERE project_id = ? AND task_id = ? ORDER BY blocked_by_task_id
            """,
            (row["project_id"], row["task_id"]),
        )
    ]
    return task


def create_remote_task(payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    title = required(payload, "title").strip()
    owner_agent_id = str(payload.get("owner_agent_id") or "").strip() or None
    status = validate_remote_task_status(payload.get("status"))
    progress_percent = validate_progress_percent(payload.get("progress_percent"))
    task_id = str(payload.get("task_id") or make_id("task"))
    ts = utc_now()
    with connect(db) as conn, transaction(conn):
        ensure_project_record(conn, project_id, ts)
        assert_project_agent(conn, project_id, owner_agent_id)
        conn.execute(
            """
            INSERT INTO tasks(
              task_id, project_id, title, summary, owner_agent_id, status,
              current_step, next_step, blocked_reason, progress_percent,
              version, created_at, updated_at, completed_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                task_id,
                project_id,
                title,
                payload.get("summary"),
                owner_agent_id,
                status,
                payload.get("current_step"),
                payload.get("next_step"),
                payload.get("blocked_reason"),
                progress_percent,
                ts,
                ts,
                ts if status in {"completed", "cancelled", "failed"} else None,
            ),
        )
        replace_task_dependencies(conn, project_id, task_id, list(payload.get("blocked_by") or []))
        if owner_agent_id:
            conn.execute(
                "UPDATE agents SET task_id = ?, status = ?, heartbeat_at = ? WHERE project_id = ? AND agent_id = ?",
                (
                    task_id,
                    "busy" if status not in {"blocked", "needs_human"} else "idle",
                    ts,
                    project_id,
                    owner_agent_id,
                ),
            )
        audit(
            conn,
            "task.created",
            {"task_id": task_id, "title": title, "status": status, "progress_percent": progress_percent},
            project_id,
            owner_agent_id,
        )
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return remote_task_to_dict(conn, row)


def update_remote_task(task_id: str, payload: dict[str, Any], db: str | None = None) -> dict[str, Any]:
    project_id = required(payload, "project_id")
    editable = {
        "title",
        "summary",
        "owner_agent_id",
        "status",
        "current_step",
        "next_step",
        "blocked_reason",
        "progress_percent",
    }
    updates = {key: payload[key] for key in editable if key in payload}
    blocked_by_supplied = "blocked_by" in payload
    if not updates and not blocked_by_supplied:
        raise RelayError("task update has no fields", code="empty_task_update")
    with connect(db) as conn, transaction(conn):
        current = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND task_id = ?",
            (project_id, task_id),
        ).fetchone()
        if not current:
            raise RelayError(f"unknown task: {task_id}", code="task_not_found")
        expected_version = payload.get("expected_version")
        if expected_version not in {None, ""} and int(expected_version) != int(current["version"]):
            raise RelayDenied(
                "task version conflict",
                {"task_id": task_id, "expected_version": int(expected_version), "actual_version": current["version"]},
                code="task_version_conflict",
            )
        if "status" in updates:
            updates["status"] = validate_remote_task_status(updates["status"])
        if "progress_percent" in updates:
            updates["progress_percent"] = validate_progress_percent(updates["progress_percent"])
        if "owner_agent_id" in updates:
            updates["owner_agent_id"] = str(updates["owner_agent_id"] or "").strip() or None
            assert_project_agent(conn, project_id, updates["owner_agent_id"])
        updates["updated_at"] = utc_now()
        updates["version"] = int(current["version"]) + 1
        next_status = str(updates.get("status") or current["status"])
        if next_status in {"completed", "cancelled", "failed"}:
            updates["completed_at"] = updates["updated_at"]
        elif current["completed_at"]:
            updates["completed_at"] = None
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE tasks SET {assignments} WHERE project_id = ? AND task_id = ?",
            (*updates.values(), project_id, task_id),
        )
        if blocked_by_supplied:
            replace_task_dependencies(conn, project_id, task_id, list(payload.get("blocked_by") or []))
        updated = conn.execute("SELECT * FROM tasks WHERE project_id = ? AND task_id = ?", (project_id, task_id)).fetchone()
        owner_agent_id = updated["owner_agent_id"]
        if owner_agent_id:
            agent_status = "idle" if next_status in {"blocked", "needs_human", "completed", "cancelled", "failed"} else "busy"
            agent_task_id = None if next_status in {"completed", "cancelled", "failed"} else task_id
            conn.execute(
                "UPDATE agents SET task_id = ?, status = ?, heartbeat_at = ? WHERE project_id = ? AND agent_id = ?",
                (agent_task_id, agent_status, utc_now(), project_id, owner_agent_id),
            )
        audit(
            conn,
            "task.updated",
            {"task_id": task_id, "changed_fields": sorted(updates), "status": next_status, "version": updates["version"]},
            project_id,
            owner_agent_id,
        )
        return remote_task_to_dict(conn, updated)


def list_remote_tasks(
    project_id: str,
    status: str | None = None,
    owner_agent_id: str | None = None,
    limit: int = 100,
    db: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM tasks WHERE project_id = ?"
    params: list[Any] = [project_id]
    if status:
        query += " AND status = ?"
        params.append(validate_remote_task_status(status))
    if owner_agent_id:
        query += " AND owner_agent_id = ?"
        params.append(owner_agent_id)
    query += " ORDER BY CASE WHEN status IN ('completed', 'cancelled', 'failed') THEN 1 ELSE 0 END, updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    with connect(db) as conn:
        return [remote_task_to_dict(conn, row) for row in conn.execute(query, params)]


def get_remote_task(project_id: str, task_id: str, db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND task_id = ?",
            (project_id, task_id),
        ).fetchone()
        if not row:
            raise RelayError(f"unknown task: {task_id}", code="task_not_found")
        return remote_task_to_dict(conn, row)


def parse_audit_payload(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def encode_console_cursor(kind: str, position: dict[str, Any]) -> str:
    raw = json.dumps({"v": 1, "kind": kind, "position": position}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_console_cursor(cursor: str | None, kind: str) -> dict[str, Any]:
    if not cursor:
        return {}
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise RelayError(
            "invalid Console cursor",
            code="invalid_cursor",
            remediation="Use the next_cursor returned by the same Console view.",
        ) from exc
    if (
        isinstance(value, dict)
        and value.get("v") == 1
        and value.get("kind") == kind
        and isinstance(value.get("position"), dict)
    ):
        return value["position"]
    raise RelayError(
        "invalid Console cursor",
        code="invalid_cursor",
        remediation="Use the next_cursor returned by the same Console view.",
    )


def console_page(items: list[dict[str, Any]], limit: int, next_cursor: str | None) -> dict[str, Any]:
    return {
        "items": items,
        "page": {
            "limit": limit,
            "returned_count": len(items),
            "has_more": next_cursor is not None,
            "next_cursor": next_cursor,
        },
    }


def console_messages(
    conn: sqlite3.Connection,
    project_id: str,
    limit: int = 80,
    audience: str = "all",
    before_sequence: int | None = None,
    query: str = "",
    agent_id: str | None = None,
    include_sequence: bool = False,
) -> list[dict[str, Any]]:
    if audience not in {"all", "broadcast", "direct"}:
        raise RelayError(f"invalid message audience: {audience}", code="invalid_message_audience")
    conditions = ["project_id = ?"]
    params: list[Any] = [project_id]
    if audience == "broadcast":
        conditions.append("recipient_agent_id IS NULL")
    elif audience == "direct":
        conditions.append("recipient_agent_id IS NOT NULL")
    if agent_id:
        conditions.append("recipient_agent_id IS NOT NULL")
        conditions.append("(sender_agent_id = ? OR recipient_agent_id = ?)")
        params.extend([agent_id, agent_id])
    if before_sequence is not None:
        conditions.append("rowid < ?")
        params.append(before_sequence)
    normalized_query = query.strip().lower()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        conditions.append(
            """
            (
              LOWER(COALESCE(body, '')) LIKE ?
              OR LOWER(COALESCE(message_type, '')) LIKE ?
              OR EXISTS (
                SELECT 1 FROM agents AS search_sender
                WHERE search_sender.project_id = messages.project_id
                  AND search_sender.agent_id = messages.sender_agent_id
                  AND LOWER(COALESCE(search_sender.handle, '')) LIKE ?
              )
            )
            """
        )
        params.extend([pattern, pattern, pattern])
    where_clause = " AND ".join(conditions)
    effective_limit = max(1, min(int(limit), 200))
    params.append(effective_limit)
    rows = conn.execute(
        f"""
        WITH selected_messages AS (
          SELECT rowid AS console_rowid, *
          FROM messages
          WHERE {where_clause}
          ORDER BY rowid DESC
          LIMIT ?
        )
        SELECT
          selected_messages.*,
          sender.handle AS sender_handle,
          sender.runtime AS sender_runtime,
          recipient.handle AS recipient_handle,
          (SELECT COUNT(*) FROM message_receipts WHERE message_id = selected_messages.message_id) AS acked_count,
          (SELECT COUNT(*) FROM message_audience WHERE message_id = selected_messages.message_id) AS audience_count
        FROM selected_messages
        LEFT JOIN agents AS sender
          ON sender.project_id = selected_messages.project_id AND sender.agent_id = selected_messages.sender_agent_id
        LEFT JOIN agents AS recipient
          ON recipient.project_id = selected_messages.project_id AND recipient.agent_id = selected_messages.recipient_agent_id
        ORDER BY selected_messages.console_rowid DESC
        """,
        params,
    )
    messages = []
    for row in rows:
        message = row_to_dict(row)
        if include_sequence:
            message["message_sequence"] = int(message.pop("console_rowid"))
        else:
            message.pop("console_rowid", None)
        messages.append(message)
    return messages


def console_messages_page(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    audience: str = "all",
    query: str = "",
    agent_id: str | None = None,
) -> dict[str, Any]:
    effective_limit = max(1, min(int(limit), 100))
    cursor_kind = f"messages:{audience}:{agent_id or 'project'}"
    position = decode_console_cursor(cursor, cursor_kind)
    before_sequence = position.get("before_sequence")
    if before_sequence is not None and (not isinstance(before_sequence, int) or before_sequence <= 0):
        raise RelayError("invalid Console message cursor", code="invalid_cursor")
    messages = console_messages(
        conn,
        project_id,
        limit=effective_limit + 1,
        audience=audience,
        before_sequence=before_sequence,
        query=query,
        agent_id=agent_id,
        include_sequence=True,
    )
    has_more = len(messages) > effective_limit
    messages = messages[:effective_limit]
    next_cursor = None
    if has_more and messages:
        next_cursor = encode_console_cursor(
            cursor_kind,
            {"before_sequence": int(messages[-1]["message_sequence"])},
        )
    for message in messages:
        message.pop("message_sequence", None)
    return console_page(messages, effective_limit, next_cursor)


def console_recent_broadcasts(conn: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        WITH selected_messages AS (
          SELECT rowid AS console_rowid, *
          FROM messages
          WHERE recipient_agent_id IS NULL
          ORDER BY rowid DESC
          LIMIT ?
        )
        SELECT
          selected_messages.*,
          sender.handle AS sender_handle,
          sender.runtime AS sender_runtime,
          projects.display_name AS project_display_name,
          (SELECT COUNT(*) FROM message_receipts WHERE message_id = selected_messages.message_id) AS acked_count,
          (SELECT COUNT(*) FROM message_audience WHERE message_id = selected_messages.message_id) AS audience_count
        FROM selected_messages
        LEFT JOIN agents AS sender
          ON sender.project_id = selected_messages.project_id AND sender.agent_id = selected_messages.sender_agent_id
        LEFT JOIN projects ON projects.project_id = selected_messages.project_id
        ORDER BY selected_messages.console_rowid DESC
        """,
        (max(1, min(int(limit), 100)),),
    )
    messages = []
    for row in rows:
        message = row_to_dict(row)
        message.pop("console_rowid", None)
        messages.append(message)
    return messages


def console_leases(
    conn: sqlite3.Connection,
    project_id: str,
    limit: int = 100,
    *,
    offset: int = 0,
    lease_filter: str = "all",
    query: str = "",
    holder_agent_id: str | None = None,
) -> list[dict[str, Any]]:
    if lease_filter not in {"all", "active"}:
        raise RelayError(f"invalid Lease filter: {lease_filter}", code="invalid_console_filter")
    timestamp = now_ts()
    conditions = ["leases.project_id = ?"]
    params: list[Any] = [project_id]
    if lease_filter == "active":
        conditions.append("leases.state = 'active' AND leases.expires_at > ?")
        params.append(timestamp)
    if holder_agent_id:
        conditions.append("leases.holder_agent_id = ?")
        params.append(holder_agent_id)
    normalized_query = query.strip().lower()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        conditions.append(
            """
            LOWER(
              COALESCE(leases.resource_id, '') || ' ' || COALESCE(leases.canonical_resource_id, '') || ' ' ||
              COALESCE(leases.mode, '') || ' ' || COALESCE(leases.reason, '') || ' ' ||
              COALESCE(agents.handle, '')
            ) LIKE ?
            """
        )
        params.append(pattern)
    params.extend([timestamp, max(1, min(int(limit), 500)), max(0, int(offset))])
    rows = conn.execute(
        f"""
        SELECT leases.*, agents.handle AS holder_handle, agents.runtime AS holder_runtime
        FROM leases
        LEFT JOIN agents
          ON agents.project_id = leases.project_id AND agents.agent_id = leases.holder_agent_id
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE WHEN leases.state = 'active' AND leases.expires_at > ? THEN 0 ELSE 1 END,
                 leases.acquired_at DESC
        LIMIT ? OFFSET ?
        """,
        params,
    )
    result = []
    for row in rows:
        item = row_to_dict(row)
        item["effective_state"] = "expired" if item["state"] == "active" and item["expires_at"] <= timestamp else item["state"]
        result.append(item)
    return result


def console_leases_page(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    lease_filter: str = "all",
    query: str = "",
) -> dict[str, Any]:
    effective_limit = max(1, min(int(limit), 100))
    position = decode_console_cursor(cursor, f"leases:{lease_filter}")
    offset = position.get("offset", 0)
    if not isinstance(offset, int) or offset < 0:
        raise RelayError("invalid Console Lease cursor", code="invalid_cursor")
    leases = console_leases(
        conn,
        project_id,
        effective_limit + 1,
        offset=offset,
        lease_filter=lease_filter,
        query=query,
    )
    has_more = len(leases) > effective_limit
    leases = leases[:effective_limit]
    next_cursor = None
    if has_more:
        next_cursor = encode_console_cursor(f"leases:{lease_filter}", {"offset": offset + effective_limit})
    return console_page(leases, effective_limit, next_cursor)


def console_activity(
    conn: sqlite3.Connection,
    project_id: str,
    limit: int = 80,
    after_event_id: int | None = None,
) -> list[dict[str, Any]]:
    comparator = ">" if after_event_id is not None else "<="
    anchor = after_event_id if after_event_id is not None else 2**63 - 1
    order = "ASC" if after_event_id is not None else "DESC"
    rows = conn.execute(
        f"""
        SELECT audit_events.*, agents.handle AS actor_handle, agents.runtime AS actor_runtime
        FROM audit_events
        LEFT JOIN agents
          ON agents.project_id = audit_events.project_id AND agents.agent_id = audit_events.actor_agent_id
        WHERE audit_events.project_id = ? AND audit_events.event_id {comparator} ?
        ORDER BY audit_events.event_id {order}
        LIMIT ?
        """,
        (project_id, anchor, max(1, min(int(limit), 500))),
    )
    events = []
    for row in rows:
        event = row_to_dict(row)
        event["payload"] = parse_audit_payload(event["payload"])
        events.append(event)
    return events


ACTIVITY_CALENDAR_DAYS = 7


def activity_category(event_type: str) -> str:
    if event_type.startswith("task"):
        return "tasks"
    if event_type.startswith("message"):
        return "messages"
    if event_type.startswith(("lease", "deploy", "operation")):
        return "leases"
    if event_type.startswith("agent"):
        return "agents"
    return "other"


def utc_day_bounds(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        raise RelayError(
            "invalid calendar date",
            code="invalid_calendar_date",
            remediation="Pass date as YYYY-MM-DD.",
        )
    try:
        parsed = datetime.strptime(normalized, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RelayError(
            "invalid calendar date",
            code="invalid_calendar_date",
            remediation="Pass date as YYYY-MM-DD.",
        ) from exc
    following = parsed + timedelta(days=1)
    return (
        parsed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        following.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )


def console_activity_calendar(
    conn: sqlite3.Connection,
    project_id: str | None = None,
    days: int = ACTIVITY_CALENDAR_DAYS,
) -> list[dict[str, Any]]:
    window = max(1, min(int(days), 31))
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=window - 1)
    end = today + timedelta(days=1)
    conditions = ["created_at >= ?", "created_at < ?"]
    params: list[Any] = [f"{start.isoformat()}T00:00:00Z", f"{end.isoformat()}T00:00:00Z"]
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    empty = {"tasks": 0, "messages": 0, "leases": 0, "agents": 0, "other": 0}
    buckets: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        f"""
        SELECT substr(created_at, 1, 10) AS day, event_type, COUNT(*) AS count
        FROM audit_events
        WHERE {' AND '.join(conditions)}
        GROUP BY day, event_type
        """,
        params,
    ):
        bucket = buckets.setdefault(str(row["day"]), dict(empty))
        event_type = str(row["event_type"])
        count = int(row["count"])
        bucket[activity_category(event_type)] += count
    calendar = []
    for offset in range(window):
        day = (start + timedelta(days=offset)).isoformat()
        bucket = buckets.get(day, empty)
        calendar.append({"date": day, "total": sum(bucket.values()), **bucket})
    return calendar


def console_day_activity(
    date: str,
    project_id: str | None = None,
    db: str | None = None,
    limit: int = 200,
    before_event_id: int | None = None,
) -> dict[str, Any]:
    normalized = str(date or "").strip()
    start_at, end_at = utc_day_bounds(normalized)
    conditions = ["audit_events.created_at >= ?", "audit_events.created_at < ?"]
    params: list[Any] = [start_at, end_at]
    if project_id:
        conditions.append("audit_events.project_id = ?")
        params.append(project_id)
    page_conditions = list(conditions)
    page_params = list(params)
    if before_event_id is not None:
        if int(before_event_id) <= 0:
            raise RelayError("invalid event cursor", code="invalid_cursor")
        page_conditions.append("audit_events.event_id < ?")
        page_params.append(int(before_event_id))
    effective_limit = max(1, min(int(limit), 500))
    page_params.append(effective_limit + 1)
    totals = {"total": 0, "tasks": 0, "messages": 0, "leases": 0, "agents": 0, "other": 0}
    events = []
    with connect(db) as conn:
        for row in conn.execute(
            f"""
            SELECT event_type, COUNT(*) AS count
            FROM audit_events
            WHERE {' AND '.join(conditions)}
            GROUP BY event_type
            """,
            params,
        ):
            count = int(row["count"])
            totals["total"] += count
            totals[activity_category(str(row["event_type"]))] += count
        rows = conn.execute(
            f"""
            SELECT audit_events.*, agents.handle AS actor_handle, agents.runtime AS actor_runtime,
                   projects.display_name AS project_display_name
            FROM audit_events
            LEFT JOIN agents
              ON agents.project_id = audit_events.project_id AND agents.agent_id = audit_events.actor_agent_id
            LEFT JOIN projects
              ON projects.project_id = audit_events.project_id
            WHERE {' AND '.join(page_conditions)}
            ORDER BY audit_events.event_id DESC
            LIMIT ?
            """,
            page_params,
        )
        for row in rows:
            event = row_to_dict(row)
            event["payload"] = parse_audit_payload(event["payload"])
            events.append(event)
    has_more = len(events) > effective_limit
    events = events[:effective_limit]
    next_cursor = str(events[-1]["event_id"]) if has_more and events else None
    return {
        "date": normalized,
        "project_id": project_id,
        "totals": totals,
        "events": events,
        "page": {
            "limit": effective_limit,
            "returned_count": len(events),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "window_complete": not has_more,
        },
    }


def console_agent_rows_to_dict(
    conn: sqlite3.Connection,
    project_id: str,
    rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    task_ids = sorted({str(row["task_id"]) for row in rows if row["task_id"]})
    tasks: dict[str, dict[str, Any]] = {}
    if task_ids:
        task_rows = list(conn.execute(
            """
            SELECT DISTINCT tasks.*
            FROM tasks
            JOIN agents
              ON agents.project_id = tasks.project_id AND agents.task_id = tasks.task_id
            WHERE agents.project_id = ?
            """,
            (project_id,),
        ))
        tasks = {str(task["task_id"]): task for task in remote_tasks_to_dict(conn, task_rows)}

    active_lease_counts = {
        str(row["holder_agent_id"]): int(row["count"])
        for row in conn.execute(
            """
            SELECT holder_agent_id, COUNT(*) AS count
            FROM leases
            WHERE project_id = ? AND state = 'active' AND expires_at > ?
            GROUP BY holder_agent_id
            """,
            (project_id, now_ts()),
        )
        if row["holder_agent_id"]
    }
    message_counts = {
        str(row["sender_agent_id"]): int(row["count"])
        for row in conn.execute(
            """
            SELECT sender_agent_id, COUNT(*) AS count
            FROM messages
            WHERE project_id = ?
            GROUP BY sender_agent_id
            """,
            (project_id,),
        )
        if row["sender_agent_id"]
    }

    agents = []
    for row in rows:
        agent = agent_with_presence(row)
        agent_id = str(row["agent_id"])
        agent["current_task"] = tasks.get(str(row["task_id"])) if row["task_id"] else None
        agent["active_lease_count"] = active_lease_counts.get(agent_id, 0)
        agent["message_count"] = message_counts.get(agent_id, 0)
        agents.append(agent)
    return agents


def console_agents(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    rows = list(conn.execute("SELECT * FROM agents WHERE project_id = ? ORDER BY heartbeat_at DESC", (project_id,)))
    return console_agent_rows_to_dict(conn, project_id, rows)


def console_agents_page(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    presence: str = "active",
    query: str = "",
) -> dict[str, Any]:
    if presence not in {"active", "all", "online", "idle", "offline"}:
        raise RelayError(f"invalid Agent presence filter: {presence}", code="invalid_console_filter")
    effective_limit = max(1, min(int(limit), 100))
    conditions = ["a.project_id = ?"]
    params: list[Any] = [project_id]
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=AGENT_RECENT_SECONDS)).isoformat().replace("+00:00", "Z")
    active_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=AGENT_ACTIVE_SECONDS)).isoformat().replace("+00:00", "Z")
    if presence == "active":
        conditions.append("a.status != 'offline' AND a.heartbeat_at >= ?")
        params.append(active_cutoff)
    elif presence == "online":
        conditions.append("a.status NOT IN ('offline', 'idle') AND a.heartbeat_at >= ?")
        params.append(recent_cutoff)
    elif presence == "idle":
        conditions.append("a.status != 'offline' AND a.heartbeat_at >= ? AND (a.status = 'idle' OR a.heartbeat_at < ?)")
        params.extend([active_cutoff, recent_cutoff])
    elif presence == "offline":
        conditions.append("(a.status = 'offline' OR a.heartbeat_at < ?)")
        params.append(active_cutoff)

    normalized_query = query.strip().lower()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        conditions.append(
            """
            LOWER(
              COALESCE(a.agent_id, '') || ' ' || COALESCE(a.handle, '') || ' ' ||
              COALESCE(a.name, '') || ' ' || COALESCE(a.runtime, '') || ' ' ||
              COALESCE(a.workspace, '') || ' ' || COALESCE(t.title, '') || ' ' ||
              COALESCE(t.current_step, '')
            ) LIKE ?
            """
        )
        params.append(pattern)

    position = decode_console_cursor(cursor, "agents")
    if position:
        heartbeat_at = position.get("heartbeat_at")
        agent_id = position.get("agent_id")
        if not isinstance(heartbeat_at, str) or not heartbeat_at or not isinstance(agent_id, str) or not agent_id:
            raise RelayError("invalid Console Agent cursor", code="invalid_cursor")
        conditions.append("(a.heartbeat_at < ? OR (a.heartbeat_at = ? AND a.agent_id > ?))")
        params.extend([heartbeat_at, heartbeat_at, agent_id])

    params.append(effective_limit + 1)
    rows = list(conn.execute(
        f"""
        SELECT a.*
        FROM agents AS a
        LEFT JOIN tasks AS t
          ON t.project_id = a.project_id AND t.task_id = a.task_id
        WHERE {' AND '.join(conditions)}
        ORDER BY a.heartbeat_at DESC, a.agent_id ASC
        LIMIT ?
        """,
        params,
    ))
    has_more = len(rows) > effective_limit
    rows = rows[:effective_limit]
    agents = console_agent_rows_to_dict(conn, project_id, rows)
    next_cursor = None
    if has_more and rows:
        next_cursor = encode_console_cursor(
            "agents",
            {"heartbeat_at": str(rows[-1]["heartbeat_at"]), "agent_id": str(rows[-1]["agent_id"])},
        )
    return console_page(agents, effective_limit, next_cursor)


def console_tasks(conn: sqlite3.Connection, project_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = list(conn.execute(
        """
        SELECT * FROM tasks WHERE project_id = ?
        ORDER BY CASE WHEN status IN ('completed', 'cancelled', 'failed') THEN 1 ELSE 0 END, updated_at DESC
        LIMIT ?
        """,
        (project_id, max(1, min(int(limit), 500))),
    ))
    return remote_tasks_to_dict(conn, rows)


def console_tasks_page(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    task_filter: str = "all",
    query: str = "",
) -> dict[str, Any]:
    if task_filter not in {"all", "active", "blocked"}:
        raise RelayError(f"invalid Task filter: {task_filter}", code="invalid_console_filter")
    effective_limit = max(1, min(int(limit), 100))
    position = decode_console_cursor(cursor, f"tasks:{task_filter}")
    offset = position.get("offset", 0)
    if not isinstance(offset, int) or offset < 0:
        raise RelayError("invalid Console Task cursor", code="invalid_cursor")
    conditions = ["project_id = ?"]
    params: list[Any] = [project_id]
    if task_filter == "active":
        conditions.append("status NOT IN ('completed', 'cancelled', 'failed')")
    elif task_filter == "blocked":
        conditions.append("status IN ('blocked', 'needs_human')")
    normalized_query = query.strip().lower()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        conditions.append(
            """
            LOWER(
              COALESCE(title, '') || ' ' || COALESCE(summary, '') || ' ' ||
              COALESCE(status, '') || ' ' || COALESCE(current_step, '')
            ) LIKE ?
            """
        )
        params.append(pattern)
    params.extend([effective_limit + 1, offset])
    rows = list(conn.execute(
        f"""
        SELECT * FROM tasks
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE WHEN status IN ('completed', 'cancelled', 'failed') THEN 1 ELSE 0 END,
                 updated_at DESC, task_id ASC
        LIMIT ? OFFSET ?
        """,
        params,
    ))
    has_more = len(rows) > effective_limit
    rows = rows[:effective_limit]
    tasks = remote_tasks_to_dict(conn, rows)
    next_cursor = None
    if has_more:
        next_cursor = encode_console_cursor(f"tasks:{task_filter}", {"offset": offset + effective_limit})
    return console_page(tasks, effective_limit, next_cursor)


def console_project_summary(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    project_id = row["project_id"]
    agents = [agent_with_presence(agent) for agent in conn.execute("SELECT * FROM agents WHERE project_id = ?", (project_id,))]
    task_rows = list(conn.execute("SELECT status, COUNT(*) AS count FROM tasks WHERE project_id = ? GROUP BY status", (project_id,)))
    task_counts = {task["status"]: int(task["count"]) for task in task_rows}
    active_task_count = sum(count for status, count in task_counts.items() if status not in {"completed", "cancelled", "failed"})
    return {
        **row_to_dict(row),
        "agent_count": len(agents),
        "active_agent_count": sum(1 for agent in agents if agent["active"]),
        "online_agent_count": sum(1 for agent in agents if agent["presence"] == "online"),
        "idle_agent_count": sum(1 for agent in agents if agent["presence"] == "idle"),
        "busy_agent_count": sum(1 for agent in agents if agent["status"] == "busy"),
        "task_count": sum(task_counts.values()),
        "active_task_count": active_task_count,
        "blocked_task_count": task_counts.get("blocked", 0) + task_counts.get("needs_human", 0),
        "active_lease_count": int(
            conn.execute(
                "SELECT COUNT(*) FROM leases WHERE project_id = ? AND state = 'active' AND expires_at > ?",
                (project_id, now_ts()),
            ).fetchone()[0]
        ),
        "message_count": int(conn.execute("SELECT COUNT(*) FROM messages WHERE project_id = ?", (project_id,)).fetchone()[0]),
        "broadcast_count": int(
            conn.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ? AND recipient_agent_id IS NULL",
                (project_id,),
            ).fetchone()[0]
        ),
        "direct_message_count": int(
            conn.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ? AND recipient_agent_id IS NOT NULL",
                (project_id,),
            ).fetchone()[0]
        ),
    }


def require_console_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    project = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    if not project:
        raise RelayError(f"unknown project: {project_id}", code="project_not_found")
    return project


def console_project_overview(conn: sqlite3.Connection, project: sqlite3.Row) -> dict[str, Any]:
    project_id = str(project["project_id"])
    agent_page = console_agents_page(conn, project_id, limit=4, presence="active")
    task_page = console_tasks_page(conn, project_id, limit=5, task_filter="active")
    broadcast_page = console_messages_page(conn, project_id, limit=3, audience="broadcast")
    return {
        "project": console_project_summary(conn, project),
        "agents": agent_page["items"],
        "tasks": task_page["items"],
        "broadcasts": broadcast_page["items"],
        "activity": console_activity(conn, project_id, limit=30),
        "activity_calendar": console_activity_calendar(conn, project_id),
    }


def console_agent_detail(
    conn: sqlite3.Connection,
    project_id: str,
    agent_id: str,
    *,
    message_limit: int = 20,
    message_cursor: str | None = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM agents WHERE project_id = ? AND agent_id = ?",
        (project_id, agent_id),
    ).fetchone()
    if not row:
        raise RelayError(f"unknown agent: {agent_id}", code="agent_not_found")
    direct_messages = console_messages_page(
        conn,
        project_id,
        limit=message_limit,
        cursor=message_cursor,
        audience="direct",
        agent_id=agent_id,
    )
    return {
        "agent": console_agent_rows_to_dict(conn, project_id, [row])[0],
        "direct_messages": direct_messages,
        "leases": console_leases(
            conn,
            project_id,
            limit=100,
            lease_filter="active",
            holder_agent_id=agent_id,
        ),
    }


def console_overview(db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        projects = [console_project_summary(conn, row) for row in conn.execute("SELECT * FROM projects ORDER BY last_activity_at DESC")]
        latest_event_id = int(conn.execute("SELECT COALESCE(MAX(event_id), 0) FROM audit_events").fetchone()[0])
        return {
            "workspace": {
                "id": os.environ.get("COMMONS_WORKSPACE_ID", "default"),
                "name": os.environ.get("COMMONS_WORKSPACE_NAME", "Commons Team"),
                "relay": "commons-relay",
            },
            "projects": projects,
            "totals": {
                "projects": len(projects),
                "agents": sum(project["agent_count"] for project in projects),
                "registered_agents": sum(project["agent_count"] for project in projects),
                "active_agents": sum(project["active_agent_count"] for project in projects),
                "online_agents": sum(project["online_agent_count"] for project in projects),
                "idle_agents": sum(project["idle_agent_count"] for project in projects),
                "active_tasks": sum(project["active_task_count"] for project in projects),
                "blocked_tasks": sum(project["blocked_task_count"] for project in projects),
                "active_leases": sum(project["active_lease_count"] for project in projects),
                "broadcasts": sum(project["broadcast_count"] for project in projects),
                "direct_messages": sum(project["direct_message_count"] for project in projects),
            },
            "recent_broadcasts": console_recent_broadcasts(conn),
            "activity_calendar": console_activity_calendar(conn),
            "latest_event_id": latest_event_id,
        }


def console_village(db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        projects = []
        for row in conn.execute("SELECT * FROM projects ORDER BY last_activity_at DESC"):
            project = console_project_summary(conn, row)
            agent_page = console_agents_page(
                conn,
                str(row["project_id"]),
                limit=CONSOLE_VILLAGE_AGENT_LIMIT,
                presence="active",
            )
            projects.append(
                {
                    "project": project,
                    "agents": agent_page["items"],
                    "recent_messages": console_messages(
                        conn,
                        str(row["project_id"]),
                        limit=CONSOLE_VILLAGE_MESSAGE_LIMIT,
                    ),
                    "has_more_agents": agent_page["page"]["has_more"],
                }
            )
        return {
            "workspace": {
                "id": os.environ.get("COMMONS_WORKSPACE_ID", "default"),
                "name": os.environ.get("COMMONS_WORKSPACE_NAME", "Commons Team"),
                "relay": "commons-relay",
            },
            "projects": projects,
            "agent_limit_per_project": CONSOLE_VILLAGE_AGENT_LIMIT,
            "generated_at": utc_now(),
        }


def console_directory(db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        project_summaries: dict[str, dict[str, Any]] = {}
        for row in conn.execute("SELECT * FROM projects ORDER BY last_activity_at DESC"):
            project_summaries[str(row["project_id"])] = console_project_summary(conn, row)
        project_names = {
            project_id: str(summary["display_name"] or project_id)
            for project_id, summary in project_summaries.items()
        }
        active_lease_counts = {
            (str(row["project_id"]), str(row["holder_agent_id"])): int(row["count"])
            for row in conn.execute(
                """
                SELECT project_id, holder_agent_id, COUNT(*) AS count
                FROM leases
                WHERE state = 'active' AND expires_at > ?
                GROUP BY project_id, holder_agent_id
                """,
                (now_ts(),),
            )
            if row["holder_agent_id"]
        }
        message_counts = {
            (str(row["project_id"]), str(row["sender_agent_id"])): int(row["count"])
            for row in conn.execute(
                """
                SELECT project_id, sender_agent_id, COUNT(*) AS count
                FROM messages
                GROUP BY project_id, sender_agent_id
                """
            )
            if row["sender_agent_id"]
        }
        users: dict[str, dict[str, Any]] = {}
        agents: list[dict[str, Any]] = []
        project_user_names: dict[str, dict[str, str | None]] = {}
        total_agents = 0
        total_active_agents = 0
        for row in conn.execute("SELECT * FROM agents ORDER BY heartbeat_at DESC"):
            agent = agent_with_presence(row)
            agent_project_id = str(row["project_id"])
            agent["project_display_name"] = project_names.get(agent_project_id, agent_project_id)
            agent["current_task"] = None
            agent["active_lease_count"] = active_lease_counts.get((agent_project_id, str(row["agent_id"])), 0)
            agent["message_count"] = message_counts.get((agent_project_id, str(row["agent_id"])), 0)
            agents.append(agent)
            slug_key = str(row["user_slug"] or "")
            project_user_names.setdefault(agent_project_id, {})[slug_key] = (
                str(row["user_name"]) if row["user_slug"] else None
            )
            total_agents += 1
            if agent["active"]:
                total_active_agents += 1
            entry = users.get(slug_key)
            if entry is None:
                entry = users[slug_key] = {
                    "user_slug": row["user_slug"],
                    "user_name": row["user_name"],
                    "agent_count": 0,
                    "active_agent_count": 0,
                    "online_agent_count": 0,
                    "runtimes": [],
                    "projects": {},
                    "last_seen_at": agent["last_seen_at"],
                    "last_seen_seconds": agent["last_seen_seconds"],
                }
            entry["agent_count"] += 1
            if agent["active"]:
                entry["active_agent_count"] += 1
            if agent["presence"] == "online":
                entry["online_agent_count"] += 1
            runtime = str(row["runtime"])
            if runtime not in entry["runtimes"]:
                entry["runtimes"].append(runtime)
            project_id = str(row["project_id"])
            project = entry["projects"].get(project_id)
            if project is None:
                project = entry["projects"][project_id] = {
                    "project_id": project_id,
                    "display_name": project_names.get(project_id, project_id),
                    "agent_count": 0,
                    "active_agent_count": 0,
                }
            project["agent_count"] += 1
            if agent["active"]:
                project["active_agent_count"] += 1
            if agent["last_seen_seconds"] < entry["last_seen_seconds"]:
                entry["last_seen_seconds"] = agent["last_seen_seconds"]
                entry["last_seen_at"] = agent["last_seen_at"]
        directory_users = []
        for entry in users.values():
            projects = sorted(
                entry["projects"].values(),
                key=lambda project: (-project["active_agent_count"], -project["agent_count"], project["display_name"]),
            )
            entry["projects"] = projects
            entry["project_count"] = len(projects)
            entry["runtimes"] = sorted(entry["runtimes"])
            directory_users.append(entry)
        directory_users.sort(
            key=lambda entry: (
                entry["user_slug"] is None,
                -entry["active_agent_count"],
                -entry["agent_count"],
                str(entry["user_name"] or "").casefold(),
            )
        )
        directory_projects = []
        for project_id, summary in project_summaries.items():
            participant_names = project_user_names.get(project_id, {})
            summary["user_count"] = sum(1 for slug in participant_names if slug)
            summary["user_names"] = sorted(
                (name for slug, name in participant_names.items() if slug and name),
                key=str.casefold,
            )
            summary["unattributed_agent_count"] = sum(
                1
                for agent in agents
                if agent["project_id"] == project_id and not agent["user_slug"]
            )
            directory_projects.append(summary)
        return {
            "workspace": {
                "id": os.environ.get("COMMONS_WORKSPACE_ID", "default"),
                "name": os.environ.get("COMMONS_WORKSPACE_NAME", "Commons Team"),
                "relay": "commons-relay",
            },
            "users": directory_users,
            "agents": agents,
            "projects": directory_projects,
            "totals": {
                "projects": len(project_names),
                "users": sum(1 for entry in directory_users if entry["user_slug"]),
                "registered_agents": total_agents,
                "active_agents": total_active_agents,
                "unattributed_agents": sum(
                    entry["agent_count"] for entry in directory_users if not entry["user_slug"]
                ),
            },
            "generated_at": utc_now(),
        }


def console_project(project_id: str, db: str | None = None) -> dict[str, Any]:
    with connect(db) as conn:
        project = require_console_project(conn, project_id)
        return {
            "project": console_project_summary(conn, project),
            "agents": console_agents(conn, project_id),
            "tasks": console_tasks(conn, project_id),
            "messages": console_messages(conn, project_id, limit=200),
            "broadcasts": console_messages(conn, project_id, limit=200, audience="broadcast"),
            "direct_messages": console_messages(conn, project_id, limit=200, audience="direct"),
            "leases": console_leases(conn, project_id),
            "activity": console_activity(conn, project_id),
        }


def encode_console_session(secret: str, expires_at: int | None = None) -> str:
    expiry = expires_at or int(time.time()) + CONSOLE_SESSION_TTL_SECONDS
    payload = f"{expiry}:{secrets.token_urlsafe(18)}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{signature}"


def verify_console_session(secret: str, value: str | None) -> bool:
    if not value or "." not in value:
        return False
    encoded, signature = value.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
        expiry_text, _nonce = payload.split(":", 1)
        expiry = int(expiry_text)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return expiry >= int(time.time()) and hmac.compare_digest(signature, expected)


def required(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or value == "":
        raise RelayError(f"missing required field: {key}")
    return str(value)


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "CommonsRelay/0.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(REQUEST_SOCKET_TIMEOUT_SECONDS)

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return

    def _send(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _db(self) -> str | None:
        return getattr(self.server, "relay_db", None)  # type: ignore[attr-defined]

    def _expected_token(self) -> str | None:
        return getattr(self.server, "relay_token", None)  # type: ignore[attr-defined]

    def _console_token(self) -> str | None:
        return getattr(self.server, "console_token", None)  # type: ignore[attr-defined]

    def _console_cookie(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get(CONSOLE_COOKIE_NAME)
        return morsel.value if morsel else None

    def _console_auth_ok(self) -> bool:
        token = self._console_token()
        return bool(token and verify_console_session(token, self._console_cookie()))

    def _require_console_auth(self) -> bool:
        if self._console_auth_ok():
            return True
        self._send(
            401,
            {
                "error": "console authentication required",
                "error_code": "console_unauthorized",
                "error_source": "commons-relay",
            },
        )
        return False

    def _console_cookie_header(self, value: str, max_age: int) -> str:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "").lower()
        secure = forwarded_proto == "https" or host not in {"localhost", "127.0.0.1", "::1"}
        attributes = [
            f"{CONSOLE_COOKIE_NAME}={value}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={max_age}",
        ]
        if secure:
            attributes.append("Secure")
        return "; ".join(attributes)

    def _auth_ok(self) -> bool:
        token = self._expected_token()
        if not token:
            return False
        header = self.headers.get("Authorization", "")
        return hmac.compare_digest(header, f"Bearer {token}")

    def _require_auth(self) -> bool:
        if self._auth_ok():
            return True
        self._send(
            401,
            {
                "error": "unauthorized",
                "error_code": "relay_unauthorized",
                "error_source": "commons-relay",
                "remediation": "Provide the relay bearer token configured for this Commons remote.",
            },
        )
        return False

    def _project_from_query(self, query: dict[str, list[str]]) -> str:
        query_project = one(query, "project_id", "")
        header_project = self.headers.get("X-Commons-Project", "").strip()
        return reconcile_project_context(query_project, header_project)

    def _project_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        body_project = str(payload.get("project_id") or "").strip()
        header_project = self.headers.get("X-Commons-Project", "").strip()
        payload["project_id"] = reconcile_project_context(body_project, header_project)
        return payload

    def _error_payload(self, exc: RelayError) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": str(exc),
            "error_code": exc.code,
            "error_source": "commons-relay",
        }
        if exc.details:
            payload["details"] = exc.details
        if exc.remediation:
            payload["remediation"] = exc.remediation
        return payload

    def _json_body(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length") or "0"
        try:
            length = int(length_text)
        except ValueError as exc:
            raise RelayError(
                "invalid Content-Length header",
                code="invalid_content_length",
                remediation="Send a decimal Content-Length header for JSON requests.",
            ) from exc
        if length < 0:
            raise RelayError("invalid Content-Length header", code="invalid_content_length")
        if length == 0:
            return {}
        if length > MAX_REQUEST_BODY_BYTES:
            raise RelayError(
                "request body exceeds the Relay limit",
                code="request_body_too_large",
                details={"max_bytes": MAX_REQUEST_BODY_BYTES, "content_length": length},
                remediation="Send a smaller coordination payload or store large evidence outside Commons.",
                status=413,
            )
        try:
            raw = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RelayError("json body must be UTF-8", code="invalid_json_encoding") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RelayError(f"invalid json: {exc}") from exc
        if not isinstance(payload, dict):
            raise RelayError("json body must be an object")
        return payload

    def _console_project_response(self, parsed_path: str, query: dict[str, list[str]]) -> Any:
        parts = [unquote(part) for part in parsed_path.strip("/").split("/")]
        if len(parts) < 4:
            raise RelayError("project id is required", code="project_context_required")
        project_id = parts[3]
        if len(parts) == 4:
            return console_project(project_id, self._db())
        view = parts[4]
        if view not in {"summary", "agents", "tasks", "messages", "broadcasts", "direct_messages", "leases", "activity"}:
            raise RelayError(f"unknown console project view: {view}", code="not_found", status=404)
        if len(parts) > 5 and not (view == "agents" and len(parts) == 6):
            raise RelayError("unknown console project resource", code="not_found", status=404)
        with connect(self._db()) as conn:
            project = require_console_project(conn, project_id)
            if view == "summary":
                return console_project_overview(conn, project)
            if view == "agents" and len(parts) == 6:
                return console_agent_detail(
                    conn,
                    project_id,
                    parts[5],
                    message_limit=int_query(query, "limit", 20, minimum=1, maximum=100),
                    message_cursor=one(query, "cursor", "") or None,
                )

            project_summary = console_project_summary(conn, project)
            paginated = any(key in query for key in {"limit", "cursor", "filter", "q"})
            if view == "agents":
                if not paginated:
                    return {"project": project_summary, "agents": console_agents(conn, project_id)}
                page = console_agents_page(
                    conn,
                    project_id,
                    limit=int_query(query, "limit", 50, minimum=1, maximum=100),
                    cursor=one(query, "cursor", "") or None,
                    presence=one(query, "filter", "active"),
                    query=one(query, "q", ""),
                )
            elif view == "tasks":
                if not paginated:
                    return {"project": project_summary, "tasks": console_tasks(conn, project_id)}
                page = console_tasks_page(
                    conn,
                    project_id,
                    limit=int_query(query, "limit", 50, minimum=1, maximum=100),
                    cursor=one(query, "cursor", "") or None,
                    task_filter=one(query, "filter", "all"),
                    query=one(query, "q", ""),
                )
            elif view in {"messages", "broadcasts", "direct_messages"}:
                audience = {"messages": "all", "broadcasts": "broadcast", "direct_messages": "direct"}[view]
                if not paginated:
                    return {"project": project_summary, view: console_messages(conn, project_id, limit=200, audience=audience)}
                page = console_messages_page(
                    conn,
                    project_id,
                    limit=int_query(query, "limit", 50, minimum=1, maximum=100),
                    cursor=one(query, "cursor", "") or None,
                    audience=audience,
                    query=one(query, "q", ""),
                )
            elif view == "leases":
                if not paginated:
                    return {"project": project_summary, "leases": console_leases(conn, project_id)}
                page = console_leases_page(
                    conn,
                    project_id,
                    limit=int_query(query, "limit", 50, minimum=1, maximum=100),
                    cursor=one(query, "cursor", "") or None,
                    lease_filter=one(query, "filter", "all"),
                    query=one(query, "q", ""),
                )
            else:
                return {
                    "project": project_summary,
                    "activity": console_activity(
                        conn,
                        project_id,
                        limit=int_query(query, "limit", 80, minimum=1, maximum=100),
                    ),
                }
            return {"project": project_summary, view: page["items"], "page": page["page"]}

    def _send_console_events(self, query: dict[str, list[str]]) -> None:
        if not self._require_console_auth():
            return
        project_id = one(query, "project_id", "") or None
        after_text = self.headers.get("Last-Event-ID") or one(query, "after", "0")
        try:
            after_event_id = max(0, int(after_text))
        except ValueError as exc:
            raise RelayError("invalid event cursor", code="invalid_pagination") from exc
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        deadline = time.time() + 25
        try:
            while time.time() < deadline:
                with connect(self._db()) as conn:
                    if project_id:
                        events = console_activity(conn, project_id, limit=100, after_event_id=after_event_id)
                    else:
                        rows = conn.execute(
                            "SELECT * FROM audit_events WHERE event_id > ? ORDER BY event_id ASC LIMIT 100",
                            (after_event_id,),
                        )
                        events = []
                        for row in rows:
                            event = row_to_dict(row)
                            event["payload"] = parse_audit_payload(event["payload"])
                            events.append(event)
                if events:
                    for event in events:
                        after_event_id = int(event["event_id"])
                        body = json.dumps(event, sort_keys=True, ensure_ascii=False)
                        self.wfile.write(f"id: {after_event_id}\nevent: activity\ndata: {body}\n\n".encode("utf-8"))
                    self.wfile.flush()
                else:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self._send(200, {"ok": True, "service": "commons-relay"})
                return
            if parsed.path == "/v1/console/events":
                self._send_console_events(query)
                return
            if parsed.path.startswith("/v1/console"):
                if not self._require_console_auth():
                    return
                if parsed.path == "/v1/console/session":
                    self._send(200, {"ok": True, "role": "operator"})
                    return
                if parsed.path in {"/v1/console/overview", "/v1/console/projects"}:
                    overview = console_overview(self._db())
                    self._send(200, overview if parsed.path.endswith("overview") else {"projects": overview["projects"]})
                    return
                if parsed.path == "/v1/console/village":
                    self._send(200, console_village(self._db()))
                    return
                if parsed.path == "/v1/console/directory":
                    self._send(200, console_directory(self._db()))
                    return
                if parsed.path == "/v1/console/day":
                    before_event_id = int_query(
                        query,
                        "before",
                        0,
                        minimum=0,
                        maximum=2**63 - 1,
                    ) or None
                    self._send(
                        200,
                        console_day_activity(
                            one(query, "date"),
                            one(query, "project_id", "") or None,
                            self._db(),
                            limit=int_query(query, "limit", 200, minimum=1, maximum=500),
                            before_event_id=before_event_id,
                        ),
                    )
                    return
                if parsed.path.startswith("/v1/console/projects/"):
                    self._send(200, self._console_project_response(parsed.path, query))
                    return
                self._send(404, {"error": "not found", "error_code": "not_found"})
                return
            if not self._require_auth():
                return
            if parsed.path == "/v1/agents":
                self._send(200, list_agents(self._project_from_query(query), self._db()))
                return
            if parsed.path == "/v1/status":
                self._send(200, relay_status(self._project_from_query(query), self._db()))
                return
            if parsed.path == "/v1/inbox":
                unread_only = one(query, "unread_only", "false").lower() == "true"
                limit = int_query(query, "limit", 50, minimum=1, maximum=MAX_QUERY_LIMIT)
                inbox_result = fetch_inbox(
                    self._project_from_query(query),
                    one(query, "agent_id"),
                    unread_only,
                    limit,
                    one(query, "cursor", "") or None,
                    one(query, "before", "") or None,
                    self._db(),
                )
                wants_envelope = one(query, "envelope", "false").lower() == "true"
                self._send(200, inbox_result if wants_envelope else inbox_result["messages"])
                return
            if parsed.path.startswith("/v1/messages/"):
                message_id = parsed.path.split("/")[3]
                self._send(
                    200,
                    get_message(
                        self._project_from_query(query),
                        message_id,
                        one(query, "agent_id"),
                        self._db(),
                    ),
                )
                return
            if parsed.path == "/v1/leases":
                active = one(query, "active", "false").lower() == "true"
                self._send(200, list_leases(self._project_from_query(query), active, self._db()))
                return
            if parsed.path == "/v1/audit":
                self._send(
                    200,
                    audit_recent(
                        self._project_from_query(query),
                        int_query(query, "limit", 50, minimum=1, maximum=500),
                        self._db(),
                    ),
                )
                return
            if parsed.path == "/v1/tasks":
                self._send(
                    200,
                    list_remote_tasks(
                        self._project_from_query(query),
                        one(query, "status", "") or None,
                        one(query, "owner_agent_id", "") or None,
                        int_query(query, "limit", 100, minimum=1, maximum=500),
                        self._db(),
                    ),
                )
                return
            if parsed.path.startswith("/v1/tasks/"):
                task_id = unquote(parsed.path.split("/")[3])
                self._send(200, get_remote_task(self._project_from_query(query), task_id, self._db()))
                return
            self._send(404, {"error": "not found"})
        except RelayDenied as exc:
            self._send(409, self._error_payload(exc))
        except RelayError as exc:
            self._send(exc.status, self._error_payload(exc))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/v1/console/session":
                token = self._console_token()
                supplied = str(self._json_body().get("token") or "")
                if not token or not supplied or not hmac.compare_digest(token, supplied):
                    self._send(
                        401,
                        {
                            "error": "invalid console access token",
                            "error_code": "console_invalid_token",
                            "error_source": "commons-relay",
                        },
                    )
                    return
                session = encode_console_session(token)
                self._send(
                    200,
                    {"ok": True, "role": "operator", "expires_in": CONSOLE_SESSION_TTL_SECONDS},
                    {"Set-Cookie": self._console_cookie_header(session, CONSOLE_SESSION_TTL_SECONDS)},
                )
                return
            if not self._require_auth():
                return
            payload = self._project_payload(self._json_body())
            if parsed.path == "/v1/agents/register":
                self._send(200, register_agent(payload, self._db()))
                return
            if parsed.path == "/v1/agents/heartbeat":
                self._send(200, heartbeat_agent(payload, self._db()))
                return
            if parsed.path == "/v1/messages":
                self._send(200, send_message(payload, self._db()))
                return
            if parsed.path.startswith("/v1/messages/") and parsed.path.endswith("/ack"):
                message_id = parsed.path.split("/")[3]
                self._send(200, ack_message(message_id, payload.get("agent_id"), self._db(), payload["project_id"]))
                return
            if parsed.path == "/v1/leases/acquire":
                self._send(200, acquire_lease(payload, self._db()))
                return
            if parsed.path == "/v1/tasks":
                self._send(201, create_remote_task(payload, self._db()))
                return
            if parsed.path.startswith("/v1/leases/") and parsed.path.endswith("/release"):
                lease_id = parsed.path.split("/")[3]
                self._send(
                    200,
                    release_lease(
                        lease_id,
                        payload.get("holder_agent_id"),
                        self._db(),
                        payload["project_id"],
                        payload.get("fencing_epoch"),
                    ),
                )
                return
            if parsed.path.startswith("/v1/leases/") and parsed.path.endswith("/renew"):
                lease_id = parsed.path.split("/")[3]
                self._send(200, renew_lease(lease_id, payload, self._db()))
                return
            self._send(404, {"error": "not found"})
        except RelayDenied as exc:
            self._send(409, self._error_payload(exc))
        except RelayError as exc:
            self._send(exc.status, self._error_payload(exc))

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if not self._require_auth():
                return
            payload = self._project_payload(self._json_body())
            if parsed.path.startswith("/v1/tasks/"):
                task_id = unquote(parsed.path.split("/")[3])
                self._send(200, update_remote_task(task_id, payload, self._db()))
                return
            self._send(404, {"error": "not found"})
        except RelayDenied as exc:
            self._send(409, self._error_payload(exc))
        except RelayError as exc:
            self._send(exc.status, self._error_payload(exc))

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/v1/console/session":
            self._send(
                200,
                {"ok": True},
                {"Set-Cookie": self._console_cookie_header("", 0)},
            )
            return
        self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def one(query: dict[str, list[str]], key: str, default: str | None = None) -> str:
    values = query.get(key)
    if values:
        return values[0]
    if default is not None:
        return default
    raise RelayError(f"missing query parameter: {key}")


def int_query(
    query: dict[str, list[str]],
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = one(query, key, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RelayError(
            f"invalid integer query parameter: {key}",
            code="invalid_query_parameter",
            details={"parameter": key, "value": raw},
            remediation=f"Pass --{key} as an integer between {minimum} and {maximum}.",
        ) from exc
    if value < minimum or value > maximum:
        raise RelayError(
            f"query parameter out of range: {key}",
            code="invalid_query_parameter",
            details={"parameter": key, "value": value, "minimum": minimum, "maximum": maximum},
            remediation=f"Pass --{key} as an integer between {minimum} and {maximum}.",
        )
    return value


def reconcile_project_context(primary: str, header: str) -> str:
    if primary and header and primary != header:
        raise RelayError(
            "project context mismatch",
            code="project_context_mismatch",
            details={"project_id": primary, "header_project": header},
            remediation="Use one --project value for the entire command.",
        )
    project = primary or header
    if not project:
        raise RelayError(
            "project context is required",
            code="project_context_required",
            remediation="Pass --project <project> or configure a default project on the remote.",
        )
    return project


def serve(host: str = "127.0.0.1", port: int = 8766, db: str | None = None, token: str | None = None) -> None:
    init_relay_db(db)
    relay_token = token or os.environ.get("COMMONS_RELAY_TOKEN")
    if not relay_token:
        raise RelayError("COMMONS_RELAY_TOKEN is required")
    console_token = os.environ.get("COMMONS_CONSOLE_TOKEN") or relay_token
    server = CommonsThreadingHTTPServer((host, port), RelayHandler)
    server.relay_db = str(relay_db(db))  # type: ignore[attr-defined]
    server.relay_token = relay_token  # type: ignore[attr-defined]
    server.console_token = console_token  # type: ignore[attr-defined]
    print(f"commons relay listening on http://{host}:{port}", flush=True)
    server.serve_forever()
