from __future__ import annotations

import json
import http.client
import os
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def local_urlopen(target: str | urllib.request.Request, timeout: float = 1):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(target, timeout=timeout)


def run_cli(home: Path, *args: str, check: bool = True, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["COMMONS_HOME"] = str(home)
    env["COMMONS_USER_NAME"] = "Test User"
    env["PYTHONPATH"] = str(ROOT)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-m", "commons.cli", "--json", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def run_cli_raw(
    home: Path,
    *args: str,
    check: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["COMMONS_HOME"] = str(home)
    env["COMMONS_USER_NAME"] = "Test User"
    env["PYTHONPATH"] = str(ROOT)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-m", "commons.cli", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def json_stdout(proc: subprocess.CompletedProcess[str]):
    return json.loads(proc.stdout)


def register_relay_agent(relay, payload: dict[str, object], relay_db: str):
    attributed = dict(payload)
    attributed.setdefault("user_name", "Test User")
    handle = str(attributed.get("handle") or attributed["agent_id"]).replace("_", "-")
    if not handle.startswith("test-user-"):
        handle = f"test-user-{handle}"
    attributed["handle"] = handle
    return relay.register_agent(attributed, relay_db)


class CommonsCoreTests(unittest.TestCase):
    def test_user_identity_configuration_and_local_agent_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".commons"
            no_identity_env = {"COMMONS_USER_NAME": ""}

            missing = json_stdout(run_cli(home, "user", "show", extra_env=no_identity_env))
            self.assertFalse(missing["configured"])

            denied = run_cli(
                home,
                "agent",
                "register",
                "--runtime",
                "codex",
                "--name",
                "reviewer",
                check=False,
                extra_env=no_identity_env,
            )
            self.assertEqual(denied.returncode, 1)
            denied_payload = json_stdout(denied)
            self.assertEqual(denied_payload["error_code"], "user_name_required")
            self.assertIn("commons user set", denied_payload["remediation"])

            configured = json_stdout(
                run_cli(
                    home,
                    "user",
                    "set",
                    "--name",
                    "Sergio Chan",
                    extra_env=no_identity_env,
                )
            )
            self.assertEqual(configured["name"], "Sergio Chan")
            self.assertEqual(configured["slug"], "sergio-chan")
            self.assertEqual((home / "user.json").stat().st_mode & 0o777, 0o600)

            loaded = json_stdout(run_cli(home, "user", "show", extra_env=no_identity_env))
            self.assertEqual(loaded["name"], "Sergio Chan")
            agent = json_stdout(
                run_cli(
                    home,
                    "agent",
                    "register",
                    "--runtime",
                    "codex",
                    "--name",
                    "reviewer",
                    extra_env=no_identity_env,
                )
            )
            self.assertEqual(agent["name"], "Sergio Chan-reviewer")
            self.assertEqual(agent["user_slug"], "sergio-chan")

    def test_relay_requires_attributed_user_prefixed_agent_handles(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "identity-relay.db")
            with self.assertRaises(relay.RelayError) as missing_identity:
                relay.register_agent(
                    {
                        "project_id": "identity",
                        "agent_id": "agent_missing_identity",
                        "runtime": "codex",
                        "handle": "codex-review",
                    },
                    relay_db,
                )
            self.assertEqual(missing_identity.exception.code, "user_name_required")

            with self.assertRaises(relay.RelayError) as wrong_prefix:
                relay.register_agent(
                    {
                        "project_id": "identity",
                        "agent_id": "agent_wrong_prefix",
                        "runtime": "codex",
                        "handle": "codex-review",
                        "user_name": "Sergio",
                    },
                    relay_db,
                )
            self.assertEqual(wrong_prefix.exception.code, "agent_handle_user_prefix_required")
            self.assertEqual(wrong_prefix.exception.details["required_prefix"], "sergio-")

            registered = relay.register_agent(
                {
                    "project_id": "identity",
                    "agent_id": "agent_sergio_review",
                    "runtime": "codex",
                    "handle": "sergio-codex-review",
                    "name": "reviewer",
                    "user_name": "Sergio",
                    "host": "sergio-mac-studio",
                },
                relay_db,
            )
            self.assertEqual(registered["handle"], "sergio-codex-review")
            self.assertEqual(registered["name"], "Sergio-reviewer")
            self.assertEqual(registered["user_name"], "Sergio")
            self.assertEqual(registered["user_slug"], "sergio")
            self.assertEqual(registered["host"], "sergio-mac-studio")

            refreshed = relay.register_agent(
                {
                    "project_id": "identity",
                    "agent_id": "agent_sergio_review",
                    "runtime": "codex",
                },
                relay_db,
            )
            self.assertEqual(refreshed["handle"], "sergio-codex-review")
            self.assertEqual(refreshed["name"], "Sergio-reviewer")
            self.assertEqual(refreshed["user_name"], "Sergio")
            self.assertEqual(refreshed["host"], "sergio-mac-studio")

            with self.assertRaises(relay.RelayError) as invalid_user_name:
                relay.register_agent(
                    {
                        "project_id": "identity",
                        "agent_id": "agent_invalid_identity",
                        "runtime": "codex",
                        "handle": "sergio-invalid",
                        "user_name": "x" * 65,
                    },
                    relay_db,
                )
            self.assertEqual(invalid_user_name.exception.code, "invalid_user_name")

            with self.assertRaises(relay.RelayError) as changed_owner:
                relay.register_agent(
                    {
                        "project_id": "identity",
                        "agent_id": "agent_sergio_review",
                        "runtime": "codex",
                        "handle": "alice-codex-review",
                        "user_name": "Alice",
                    },
                    relay_db,
                )
            self.assertEqual(changed_owner.exception.code, "agent_user_identity_conflict")

    def test_relay_can_temporarily_accept_legacy_registration_during_user_prefix_rollout(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"COMMONS_REQUIRE_USER_PREFIX": "false"},
        ):
            relay_db = str(Path(td) / "identity-rollout-relay.db")
            legacy = relay.register_agent(
                {
                    "project_id": "identity-rollout",
                    "agent_id": "agent_legacy_client",
                    "runtime": "codex",
                    "handle": "codex-legacy-client",
                    "name": "Legacy Client",
                },
                relay_db,
            )
            self.assertEqual(legacy["handle"], "codex-legacy-client")
            self.assertEqual(legacy["name"], "Legacy Client")
            self.assertIsNone(legacy["user_name"])
            self.assertIsNone(legacy["user_slug"])

            attributed = relay.register_agent(
                {
                    "project_id": "identity-rollout",
                    "agent_id": "agent_attributed_client",
                    "runtime": "codex",
                    "handle": "sergio-codex-client",
                    "name": "client",
                    "user_name": "Sergio",
                },
                relay_db,
            )
            self.assertEqual(attributed["handle"], "sergio-codex-client")
            self.assertEqual(attributed["name"], "Sergio-client")
            self.assertEqual(attributed["user_name"], "Sergio")
            self.assertEqual(attributed["user_slug"], "sergio")

    def test_relay_grandfathers_existing_unattributed_agent(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "legacy-agent.db")
            with sqlite3.connect(relay_db) as conn:
                conn.execute(
                    """
                    CREATE TABLE agents (
                      project_id TEXT NOT NULL,
                      agent_id TEXT NOT NULL,
                      handle TEXT,
                      contact_code TEXT,
                      name TEXT,
                      runtime TEXT NOT NULL,
                      workspace TEXT,
                      task_id TEXT,
                      status TEXT NOT NULL DEFAULT 'online',
                      registered_at TEXT NOT NULL,
                      heartbeat_at TEXT NOT NULL,
                      PRIMARY KEY(project_id, agent_id)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO agents(
                      project_id, agent_id, handle, contact_code, name, runtime,
                      status, registered_at, heartbeat_at
                    ) VALUES(
                      'legacy', 'legacy_agent', 'codex-old', 'LEGACY', 'Old Agent',
                      'codex', 'online', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
                    )
                    """
                )

            relay.init_relay_db(relay_db)
            with relay.connect(relay_db) as conn:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(agents)")}
            self.assertIn("user_name", columns)
            self.assertIn("user_slug", columns)
            self.assertIn("host", columns)

            refreshed = relay.register_agent(
                {"project_id": "legacy", "agent_id": "legacy_agent", "runtime": "codex"},
                relay_db,
            )
            self.assertEqual(refreshed["handle"], "codex-old")
            self.assertIsNone(refreshed["user_name"])

    def test_console_large_project_queries_are_bounded(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "console-large.db")
            project_id = "console-large"
            for index in range(40):
                register_relay_agent(
                    relay,
                    {
                        "project_id": project_id,
                        "agent_id": f"agent_{index:02d}",
                        "runtime": "codex",
                        "handle": f"agent-{index:02d}",
                    },
                    relay_db,
                )
            task = relay.create_remote_task(
                {
                    "project_id": project_id,
                    "title": "Profile a large Console project",
                    "owner_agent_id": "agent_00",
                    "status": "in_progress",
                    "blocked_by": [],
                },
                relay_db,
            )
            lease = relay.acquire_lease(
                {
                    "project_id": project_id,
                    "resource_id": "path:console-large/shared",
                    "holder_agent_id": "agent_00",
                    "mode": "exclusive",
                    "ttl": "30m",
                },
                relay_db,
            )
            latest_message = None
            for index in range(220):
                latest_message = relay.send_message(
                    {
                        "project_id": project_id,
                        "sender_agent_id": f"agent_{index % 40:02d}",
                        "recipient": "broadcast",
                        "message_type": "status",
                        "body": f"Large project status {index}",
                    },
                    relay_db,
                )
            assert latest_message is not None
            relay.ack_message(latest_message["message_id"], "agent_01", relay_db, project_id)

            with relay.connect(relay_db) as conn:
                selects = 0

                def trace(statement: str) -> None:
                    nonlocal selects
                    if statement.lstrip().upper().startswith("SELECT"):
                        selects += 1

                conn.set_trace_callback(trace)
                agents = relay.console_agents(conn, project_id)
                conn.set_trace_callback(None)
                broadcasts = relay.console_messages(conn, project_id, limit=200, audience="broadcast")

            self.assertLessEqual(selects, 8)
            self.assertEqual(len(agents), 40)
            owner = next(agent for agent in agents if agent["agent_id"] == "agent_00")
            self.assertEqual(owner["current_task"]["task_id"], task["task_id"])
            self.assertEqual(owner["active_lease_count"], 1)
            self.assertEqual(owner["message_count"], 6)
            self.assertEqual(len(broadcasts), 200)
            self.assertEqual(broadcasts[0]["message_id"], latest_message["message_id"])
            self.assertEqual(broadcasts[0]["audience_count"], 39)
            self.assertEqual(broadcasts[0]["acked_count"], 1)
            self.assertEqual(lease["state"], "active")

    def test_console_activity_calendar_buckets_events_by_day(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "console-calendar.db")
            register_relay_agent(
                relay,
                {"project_id": "demo", "agent_id": "agent_a", "runtime": "codex"},
                relay_db,
            )
            relay.create_remote_task(
                {
                    "project_id": "demo",
                    "title": "Calendar fixture task",
                    "owner_agent_id": "agent_a",
                    "status": "in_progress",
                    "blocked_by": [],
                },
                relay_db,
            )
            relay.send_message(
                {
                    "project_id": "demo",
                    "sender_agent_id": "agent_a",
                    "recipient": "broadcast",
                    "message_type": "status",
                    "body": "Calendar fixture broadcast",
                },
                relay_db,
            )
            two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.execute(
                    """
                    INSERT INTO audit_events(project_id, event_type, actor_agent_id, payload, created_at)
                    VALUES('demo', 'lease.granted', 'agent_a', '{}', ?)
                    """,
                    (two_days_ago,),
                )

            overview = relay.console_overview(relay_db)
            calendar = overview["activity_calendar"]
            self.assertEqual(len(calendar), relay.ACTIVITY_CALENDAR_DAYS)
            today = calendar[-1]
            self.assertEqual(today["date"], datetime.now(timezone.utc).date().isoformat())
            self.assertGreaterEqual(today["agents"], 1)
            self.assertGreaterEqual(today["tasks"], 1)
            self.assertGreaterEqual(today["messages"], 1)
            backdated = calendar[-3]
            self.assertEqual(backdated["date"], two_days_ago[:10])
            self.assertEqual(backdated["leases"], 1)
            self.assertEqual(backdated["total"], 1)
            self.assertEqual(calendar[0]["total"], 0)

            with relay.connect(relay_db) as conn:
                project = relay.require_console_project(conn, "demo")
                detail = relay.console_project_overview(conn, project)
            self.assertEqual(len(detail["activity_calendar"]), relay.ACTIVITY_CALENDAR_DAYS)
            self.assertEqual(detail["activity_calendar"][-3]["leases"], 1)

            today_detail = relay.console_day_activity(
                datetime.now(timezone.utc).date().isoformat(),
                db=relay_db,
            )
            self.assertGreaterEqual(today_detail["totals"]["tasks"], 1)
            self.assertGreaterEqual(today_detail["totals"]["messages"], 1)
            self.assertGreaterEqual(today_detail["totals"]["agents"], 1)
            self.assertEqual(today_detail["totals"]["total"], len(today_detail["events"]))
            self.assertTrue(all(event["created_at"][:10] == today_detail["date"] for event in today_detail["events"]))
            self.assertTrue(any(event["actor_handle"] for event in today_detail["events"]))
            self.assertTrue(any(event["project_display_name"] == "Demo" for event in today_detail["events"]))

            backdated_detail = relay.console_day_activity(two_days_ago[:10], "demo", relay_db)
            self.assertEqual(backdated_detail["totals"]["total"], 1)
            self.assertEqual(backdated_detail["totals"]["leases"], 1)
            self.assertEqual(backdated_detail["events"][0]["event_type"], "lease.granted")

            empty_detail = relay.console_day_activity(two_days_ago[:10], "other-project", relay_db)
            self.assertEqual(empty_detail["totals"]["total"], 0)

            with self.assertRaises(relay.RelayError):
                relay.console_day_activity("not-a-date", db=relay_db)
            with self.assertRaises(relay.RelayError):
                relay.console_day_activity("2026-8-04", db=relay_db)

            overflow_day = datetime.now(timezone.utc).date().isoformat()
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.executemany(
                    """
                    INSERT INTO audit_events(project_id, event_type, actor_agent_id, payload, created_at)
                    VALUES('overflow', 'message.sent', 'agent_a', '{}', ?)
                    """,
                    [(f"{overflow_day}T12:00:00Z",)] * 250,
                )
            first_page = relay.console_day_activity(overflow_day, "overflow", relay_db, limit=100)
            self.assertEqual(first_page["totals"]["total"], 250)
            self.assertEqual(first_page["totals"]["messages"], 250)
            self.assertEqual(len(first_page["events"]), 100)
            self.assertFalse(first_page["page"]["window_complete"])
            self.assertIsNotNone(first_page["page"]["next_cursor"])
            second_page = relay.console_day_activity(
                overflow_day,
                "overflow",
                relay_db,
                limit=100,
                before_event_id=int(first_page["page"]["next_cursor"]),
            )
            third_page = relay.console_day_activity(
                overflow_day,
                "overflow",
                relay_db,
                limit=100,
                before_event_id=int(second_page["page"]["next_cursor"]),
            )
            event_ids = {
                event["event_id"]
                for page in (first_page, second_page, third_page)
                for event in page["events"]
            }
            self.assertEqual(len(event_ids), 250)
            self.assertTrue(third_page["page"]["window_complete"])

            with relay.connect(relay_db) as conn:
                workspace_plan = " ".join(
                    str(row["detail"])
                    for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT event_type, COUNT(*) FROM audit_events WHERE created_at >= ? AND created_at < ? GROUP BY event_type",
                        (f"{overflow_day}T00:00:00Z", f"{overflow_day}T23:59:59Z"),
                    )
                )
                project_plan = " ".join(
                    str(row["detail"])
                    for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT event_type, COUNT(*) FROM audit_events WHERE project_id = ? AND created_at >= ? AND created_at < ? GROUP BY event_type",
                        ("overflow", f"{overflow_day}T00:00:00Z", f"{overflow_day}T23:59:59Z"),
                    )
                )
            self.assertIn("idx_audit_created_at", workspace_plan)
            self.assertIn("idx_audit_project_created_at", project_plan)

    def test_console_directory_groups_agents_by_user(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "console-directory.db")
            relay.register_agent(
                {
                    "project_id": "checkout",
                    "agent_id": "ada_codex",
                    "runtime": "codex",
                    "handle": "ada-lovelace-codex",
                    "user_name": "Ada Lovelace",
                },
                relay_db,
            )
            relay.register_agent(
                {
                    "project_id": "checkout",
                    "agent_id": "ada_claude",
                    "runtime": "claude-code",
                    "handle": "ada-lovelace-claude",
                    "user_name": "Ada Lovelace",
                },
                relay_db,
            )
            relay.register_agent(
                {
                    "project_id": "payments",
                    "agent_id": "ada_reviewer",
                    "runtime": "codex",
                    "handle": "ada-lovelace-reviewer",
                    "user_name": "Ada Lovelace",
                },
                relay_db,
            )
            relay.register_agent(
                {
                    "project_id": "payments",
                    "agent_id": "grace_claude",
                    "runtime": "claude-code",
                    "handle": "grace-hopper-claude",
                    "user_name": "Grace Hopper",
                },
                relay_db,
            )
            relay.heartbeat_agent(
                {"project_id": "payments", "agent_id": "grace_claude", "status": "offline"},
                relay_db,
            )
            relay.create_remote_task(
                {
                    "project_id": "checkout",
                    "title": "Directory task fixture",
                    "owner_agent_id": "ada_codex",
                    "status": "in_progress",
                },
                relay_db,
            )
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.execute(
                    """
                    INSERT INTO agents(
                      project_id, agent_id, handle, contact_code, name, runtime,
                      status, registered_at, heartbeat_at
                    ) VALUES(
                      'checkout', 'legacy_agent', 'codex-legacy', 'LEGACY', 'Legacy Agent',
                      'codex', 'online', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
                    )
                    """
                )

            directory = relay.console_directory(relay_db)

            self.assertEqual(directory["totals"]["projects"], 2)
            self.assertEqual(directory["totals"]["users"], 2)
            self.assertEqual(directory["totals"]["registered_agents"], 5)
            self.assertEqual(directory["totals"]["active_agents"], 3)
            self.assertEqual(directory["totals"]["unattributed_agents"], 1)

            ada = directory["users"][0]
            self.assertEqual(ada["user_slug"], "ada-lovelace")
            self.assertEqual(ada["user_name"], "Ada Lovelace")
            self.assertEqual(ada["agent_count"], 3)
            self.assertEqual(ada["active_agent_count"], 3)
            self.assertEqual(ada["project_count"], 2)
            self.assertEqual(ada["runtimes"], ["claude-code", "codex"])
            self.assertEqual(
                {project["project_id"] for project in ada["projects"]},
                {"checkout", "payments"},
            )

            grace = next(entry for entry in directory["users"] if entry["user_slug"] == "grace-hopper")
            self.assertEqual(grace["agent_count"], 1)
            self.assertEqual(grace["active_agent_count"], 0)
            self.assertEqual(grace["project_count"], 1)

            unattributed = next(entry for entry in directory["users"] if not entry["user_slug"])
            self.assertIsNone(unattributed["user_name"])
            self.assertEqual(unattributed["agent_count"], 1)
            self.assertEqual(unattributed["active_agent_count"], 0)

            self.assertEqual(len(directory["agents"]), 5)
            ada_codex = next(agent for agent in directory["agents"] if agent["agent_id"] == "ada_codex")
            self.assertEqual(ada_codex["user_name"], "Ada Lovelace")
            self.assertEqual(ada_codex["user_slug"], "ada-lovelace")
            self.assertEqual(ada_codex["project_display_name"], "Checkout")
            legacy_agent = next(agent for agent in directory["agents"] if agent["agent_id"] == "legacy_agent")
            self.assertIsNone(legacy_agent["user_slug"])
            self.assertEqual(legacy_agent["presence"], "offline")

            self.assertEqual(len(directory["projects"]), 2)
            checkout = next(project for project in directory["projects"] if project["project_id"] == "checkout")
            self.assertEqual(checkout["user_count"], 1)
            self.assertEqual(checkout["user_names"], ["Ada Lovelace"])
            self.assertEqual(checkout["unattributed_agent_count"], 1)
            self.assertEqual(checkout["agent_count"], 3)
            self.assertEqual(checkout["task_count"], 1)
            payments = next(project for project in directory["projects"] if project["project_id"] == "payments")
            self.assertEqual(payments["user_count"], 2)
            self.assertEqual(payments["user_names"], ["Ada Lovelace", "Grace Hopper"])
            self.assertEqual(payments["unattributed_agent_count"], 0)

    def test_remote_loopback_requests_bypass_proxies(self) -> None:
        from commons import remote

        loopback_request = urllib.request.Request("http://127.0.0.1:8766/health")
        loopback_opener = mock.Mock()
        loopback_response = object()
        loopback_opener.open.return_value = loopback_response
        with mock.patch.object(remote, "build_opener", return_value=loopback_opener) as build_opener:
            self.assertIs(remote.open_request(loopback_request, timeout=2), loopback_response)
        build_opener.assert_called_once()
        loopback_opener.open.assert_called_once_with(loopback_request, timeout=2)

        public_request = urllib.request.Request("https://commons.example/health")
        public_response = object()
        with mock.patch.object(remote, "urlopen", return_value=public_response) as public_open:
            self.assertIs(remote.open_request(public_request, timeout=3), public_response)
        public_open.assert_called_once_with(public_request, timeout=3)

    def test_http_servers_do_not_require_reverse_dns(self) -> None:
        from http.server import BaseHTTPRequestHandler

        from commons.http_server import CommonsThreadingHTTPServer

        with mock.patch("socket.getfqdn", side_effect=AssertionError("reverse DNS must not run")):
            server = CommonsThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        try:
            self.assertEqual(server.server_name, "127.0.0.1")
            self.assertGreater(server.server_port, 0)
        finally:
            server.server_close()

    def test_database_contexts_close_connections(self) -> None:
        from commons import db as local_db
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            local_path = root / "local.db"
            local_db.init_db(local_path)
            with local_db.connect(local_path) as local_connection:
                local_connection.execute("SELECT 1").fetchone()
            with self.assertRaises(sqlite3.ProgrammingError):
                local_connection.execute("SELECT 1")

            relay_path = root / "relay.db"
            with relay.connect(str(relay_path)) as relay_connection:
                relay_connection.execute("SELECT 1").fetchone()
            with self.assertRaises(sqlite3.ProgrammingError):
                relay_connection.execute("SELECT 1")

    def test_relay_agent_activity_window_and_task_evidence(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "activity-relay.db")
            register_relay_agent(
                relay,
                {"project_id": "activity", "agent_id": "worker", "runtime": "codex"},
                relay_db,
            )
            stale = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat().replace("+00:00", "Z")
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.execute(
                    "UPDATE agents SET heartbeat_at = ?, status = 'online' WHERE project_id = 'activity' AND agent_id = 'worker'",
                    (stale,),
                )
            stale_agent = relay.list_agents("activity", relay_db)[0]
            self.assertFalse(stale_agent["active"])
            self.assertEqual(stale_agent["presence"], "offline")

            relay.create_remote_task(
                {
                    "project_id": "activity",
                    "title": "Refresh activity through task creation",
                    "owner_agent_id": "worker",
                    "status": "in_progress",
                },
                relay_db,
            )
            working_agent = relay.list_agents("activity", relay_db)[0]
            self.assertTrue(working_agent["active"])
            self.assertEqual(working_agent["presence"], "online")

            recent = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.execute(
                    "UPDATE agents SET heartbeat_at = ?, status = 'busy' WHERE project_id = 'activity' AND agent_id = 'worker'",
                    (recent,),
                )
            recent_agent = relay.list_agents("activity", relay_db)[0]
            self.assertTrue(recent_agent["active"])
            self.assertEqual(recent_agent["presence"], "idle")

            stopped_agent = relay.heartbeat_agent(
                {"project_id": "activity", "agent_id": "worker", "status": "offline"},
                relay_db,
            )
            self.assertFalse(stopped_agent["active"])
            self.assertEqual(stopped_agent["presence"], "offline")

    def test_relay_message_audience_migration_is_idempotent(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "legacy-relay.db")
            with sqlite3.connect(relay_db) as conn:
                conn.executescript(relay.RELAY_SCHEMA)
                conn.execute(
                    """
                    INSERT INTO agents(project_id, agent_id, runtime, status, registered_at, heartbeat_at)
                    VALUES('legacy', 'sender', 'codex', 'online', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO agents(project_id, agent_id, runtime, status, registered_at, heartbeat_at)
                    VALUES('legacy', 'reader', 'claude-code', 'online', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO messages(message_id, project_id, thread_id, sender_agent_id, message_type, body, acked_at, created_at)
                    VALUES('msg_legacy', 'legacy', 'thread_legacy', 'sender', 'broadcast', 'legacy body', '2026-01-02T00:01:00Z', '2026-01-02T00:00:00Z')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO audit_events(project_id, event_type, actor_agent_id, payload, created_at)
                    VALUES('legacy', 'message.acked', 'reader', '{"message_id":"msg_legacy"}', '2026-01-02T00:01:00Z')
                    """
                )

            relay.init_relay_db(relay_db)
            relay.init_relay_db(relay_db)
            with relay.connect(relay_db) as conn:
                audience = list(conn.execute("SELECT * FROM message_audience WHERE message_id = 'msg_legacy'"))
                marker = conn.execute(
                    "SELECT value FROM relay_meta WHERE key = 'message_audience_backfill_v1'"
                ).fetchone()
                receipt = conn.execute(
                    "SELECT agent_id FROM message_receipts WHERE message_id = 'msg_legacy'"
                ).fetchone()
            self.assertEqual([row["agent_id"] for row in audience], ["reader"])
            self.assertIsNotNone(marker)
            self.assertEqual(receipt["agent_id"], "reader")

    def test_relay_message_policy_migrates_legacy_rows(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "legacy-message-policy.db")
            with sqlite3.connect(relay_db) as conn:
                conn.execute(
                    """
                    CREATE TABLE messages (
                      message_id TEXT PRIMARY KEY,
                      project_id TEXT NOT NULL,
                      thread_id TEXT NOT NULL,
                      sender_agent_id TEXT,
                      recipient_agent_id TEXT,
                      message_type TEXT NOT NULL DEFAULT 'note',
                      body TEXT NOT NULL,
                      acked_at TEXT,
                      created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO messages(
                      message_id, project_id, thread_id, sender_agent_id,
                      recipient_agent_id, message_type, body, created_at
                    ) VALUES('legacy_direct', 'legacy', 'thread_direct', 'sender', 'reader', 'note', 'direct', '2026-01-01T00:00:00Z')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO messages(
                      message_id, project_id, thread_id, sender_agent_id,
                      recipient_agent_id, message_type, body, created_at
                    ) VALUES('legacy_broadcast', 'legacy', 'thread_broadcast', 'sender', NULL, 'note', 'broadcast', '2026-01-01T00:00:00Z')
                    """
                )

            relay.init_relay_db(relay_db)
            with relay.connect(relay_db) as conn:
                policies = {
                    row["message_id"]: row["audience_policy"]
                    for row in conn.execute("SELECT message_id, audience_policy FROM messages")
                }
            self.assertEqual(policies["legacy_direct"], "direct_recipient")
            self.assertEqual(policies["legacy_broadcast"], "legacy_registered_at_send")

    def test_relay_broadcast_targets_only_active_agents_at_send(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "active-audience.db")
            for agent_id in ("sender", "active", "offline", "stale"):
                register_relay_agent(
                    relay,
                    {"project_id": "audience", "agent_id": agent_id, "runtime": "codex"},
                    relay_db,
                )
            relay.heartbeat_agent(
                {"project_id": "audience", "agent_id": "offline", "status": "offline"},
                relay_db,
            )
            stale_at = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat().replace("+00:00", "Z")
            with relay.connect(relay_db) as conn, relay.transaction(conn):
                conn.execute(
                    "UPDATE agents SET heartbeat_at = ? WHERE project_id = 'audience' AND agent_id = 'stale'",
                    (stale_at,),
                )

            message = relay.send_message(
                {"project_id": "audience", "sender_agent_id": "sender", "recipient": "broadcast", "body": "plan"},
                relay_db,
            )
            stored = relay.get_message("audience", message["message_id"], "sender", relay_db)
            self.assertEqual(stored["audience_policy"], "active_agents_at_send")
            self.assertEqual(stored["receipt_summary"]["audience_policy"], "active_agents_at_send")
            self.assertEqual(stored["receipt_summary"]["eligible_agent_count"], 1)
            self.assertEqual(len(relay.fetch_inbox("audience", "active", db=relay_db)["messages"]), 1)
            self.assertEqual(relay.fetch_inbox("audience", "offline", db=relay_db)["messages"], [])
            self.assertEqual(relay.fetch_inbox("audience", "stale", db=relay_db)["messages"], [])

            register_relay_agent(
                relay,
                {"project_id": "audience", "agent_id": "late", "runtime": "claude-code"},
                relay_db,
            )
            self.assertEqual(relay.fetch_inbox("audience", "late", db=relay_db)["messages"], [])
            relay.ack_message(message["message_id"], "active", relay_db, "audience")
            acknowledged = relay.get_message("audience", message["message_id"], "sender", relay_db)
            self.assertTrue(acknowledged["receipt_summary"]["all_acked"])

    def test_relay_initialization_runs_once_under_concurrency(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "relay.db")
            with mock.patch(
                "commons.relay.normalize_existing_resources",
                wraps=relay.normalize_existing_resources,
            ) as normalize:
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda _: relay.init_relay_db(relay_db), range(16)))
            self.assertEqual(normalize.call_count, 1)

    def test_relay_resource_migration_rejects_active_collision(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "legacy-resources.db")
            expires_at = time.time() + 3600
            with sqlite3.connect(relay_db) as conn:
                conn.executescript(relay.RELAY_SCHEMA)
                conn.execute(
                    """
                    INSERT INTO resources(project_id, canonical_id, fencing_epoch, created_at, updated_at)
                    VALUES('demo', 'DEPLOY-SLOT:Demo//Staging/', 4, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO resources(project_id, canonical_id, fencing_epoch, created_at, updated_at)
                    VALUES('demo', 'deploy-slot:demo/staging', 7, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                    """
                )
                for lease_id, canonical, epoch in (
                    ("lease_legacy", "DEPLOY-SLOT:Demo//Staging/", 4),
                    ("lease_canonical", "deploy-slot:demo/staging", 7),
                ):
                    conn.execute(
                        """
                        INSERT INTO leases(
                          lease_id, project_id, resource_id, canonical_resource_id, mode,
                          holder_agent_id, state, fencing_epoch, acquired_at, expires_at
                        ) VALUES(?, 'demo', ?, ?, 'exclusive', ?, 'active', ?, '2026-01-01T00:00:00Z', ?)
                        """,
                        (lease_id, canonical, canonical, lease_id, epoch, expires_at),
                    )

            with self.assertRaises(relay.RelayError) as raised:
                relay.init_relay_db(relay_db)
            self.assertEqual(raised.exception.code, "resource_migration_conflict")
            with sqlite3.connect(relay_db) as conn:
                active_count = conn.execute("SELECT COUNT(*) FROM leases WHERE state = 'active'").fetchone()[0]
            self.assertEqual(active_count, 2)

    def test_relay_lease_ownership_and_fencing(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "relay.db")
            register_relay_agent(
                relay, {"project_id": "demo", "agent_id": "writer", "runtime": "codex"}, relay_db
            )
            register_relay_agent(
                relay, {"project_id": "demo", "agent_id": "observer", "runtime": "claude-code"}, relay_db
            )

            with self.assertRaises(relay.RelayError):
                relay.acquire_lease({"project_id": "demo", "resource_id": "db:demo/staging"}, relay_db)
            with self.assertRaises(relay.RelayError):
                relay.acquire_lease(
                    {
                        "project_id": "demo",
                        "resource_id": "db:demo/staging",
                        "holder_agent_id": "unknown",
                    },
                    relay_db,
                )

            writer = relay.acquire_lease(
                {
                    "project_id": "demo",
                    "resource_id": "db:demo/staging",
                    "mode": "write",
                    "holder_agent_id": "writer",
                },
                relay_db,
            )
            observer = relay.acquire_lease(
                {
                    "project_id": "demo",
                    "resource_id": "DB:demo//staging/",
                    "mode": "observe",
                    "holder_agent_id": "observer",
                },
                relay_db,
            )
            self.assertEqual(observer["fencing_epoch"], writer["fencing_epoch"])

            with self.assertRaises(relay.RelayError):
                relay.release_lease(writer["lease_id"], "writer", relay_db, "demo")
            with self.assertRaises(relay.RelayDenied):
                relay.release_lease(writer["lease_id"], "observer", relay_db, "demo", writer["fencing_epoch"])
            with self.assertRaises(relay.RelayDenied):
                relay.release_lease(writer["lease_id"], "writer", relay_db, "demo", writer["fencing_epoch"] + 1)

            released = relay.release_lease(
                writer["lease_id"],
                "writer",
                relay_db,
                "demo",
                writer["fencing_epoch"],
            )
            repeated = relay.release_lease(
                writer["lease_id"],
                "writer",
                relay_db,
                "demo",
                writer["fencing_epoch"],
            )
            self.assertTrue(released["newly_released"])
            self.assertFalse(repeated["newly_released"])
            with relay.connect(relay_db) as conn:
                release_events = conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE event_type = 'lease.released' AND resource_id = 'db:demo/staging'"
                ).fetchone()[0]
            self.assertEqual(release_events, 1)

    def test_relay_lease_renewal_is_atomic_and_fenced(self) -> None:
        from commons import relay

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "relay.db")
            register_relay_agent(
                relay, {"project_id": "renewal", "agent_id": "holder", "runtime": "codex"}, relay_db
            )
            register_relay_agent(
                relay, {"project_id": "renewal", "agent_id": "other", "runtime": "claude-code"}, relay_db
            )
            lease = relay.acquire_lease(
                {
                    "project_id": "renewal",
                    "resource_id": "deploy-slot:demo/staging",
                    "mode": "exclusive",
                    "holder_agent_id": "holder",
                    "ttl": "1m",
                },
                relay_db,
            )

            with self.assertRaises(relay.RelayDenied) as already_held:
                relay.acquire_lease(
                    {
                        "project_id": "renewal",
                        "resource_id": "DEPLOY-SLOT:demo//staging/",
                        "mode": "exclusive",
                        "holder_agent_id": "holder",
                        "ttl": "2h",
                    },
                    relay_db,
                )
            self.assertEqual(already_held.exception.code, "lease_already_held")
            self.assertTrue(already_held.exception.details["same_holder"])
            renew_action = shlex.split(already_held.exception.details["safe_next_actions"][0])
            self.assertEqual(renew_action[:4], ["commons", "remote", "lease", "renew"])
            self.assertIn(str(lease["fencing_epoch"]), renew_action)

            with self.assertRaises(relay.RelayError) as missing_epoch:
                relay.renew_lease(
                    lease["lease_id"],
                    {
                        "project_id": "renewal",
                        "holder_agent_id": "holder",
                        "ttl": "2h",
                    },
                    relay_db,
                )
            self.assertEqual(missing_epoch.exception.code, "fencing_epoch_required")

            with self.assertRaises(relay.RelayDenied):
                relay.renew_lease(
                    lease["lease_id"],
                    {
                        "project_id": "renewal",
                        "holder_agent_id": "other",
                        "fencing_epoch": lease["fencing_epoch"],
                        "ttl": "2h",
                    },
                    relay_db,
                )
            with self.assertRaises(relay.RelayDenied) as stale_epoch:
                relay.renew_lease(
                    lease["lease_id"],
                    {
                        "project_id": "renewal",
                        "holder_agent_id": "holder",
                        "fencing_epoch": lease["fencing_epoch"] + 1,
                        "ttl": "2h",
                    },
                    relay_db,
                )
            self.assertEqual(stale_epoch.exception.code, "stale_fencing_epoch")

            renewed = relay.renew_lease(
                lease["lease_id"],
                {
                    "project_id": "renewal",
                    "holder_agent_id": "holder",
                    "fencing_epoch": lease["fencing_epoch"],
                    "ttl": "2h",
                },
                relay_db,
            )
            self.assertEqual(renewed["lease_id"], lease["lease_id"])
            self.assertEqual(renewed["fencing_epoch"], lease["fencing_epoch"])
            self.assertEqual(renewed["ttl_seconds"], 7200)
            self.assertGreater(renewed["expires_at"], lease["expires_at"])
            with relay.connect(relay_db) as conn:
                active_count = conn.execute(
                    "SELECT COUNT(*) FROM leases WHERE project_id = 'renewal' AND state = 'active'"
                ).fetchone()[0]
                renewal_events = conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE event_type = 'lease.renewed' AND resource_id = 'deploy-slot:demo/staging'"
                ).fetchone()[0]
                conn.execute("UPDATE leases SET expires_at = ? WHERE lease_id = ?", (time.time() - 1, lease["lease_id"]))
                conn.commit()
            self.assertEqual(active_count, 1)
            self.assertEqual(renewal_events, 1)

            with self.assertRaises(relay.RelayDenied) as inactive:
                relay.renew_lease(
                    lease["lease_id"],
                    {
                        "project_id": "renewal",
                        "holder_agent_id": "holder",
                        "fencing_epoch": lease["fencing_epoch"],
                        "ttl": "2h",
                    },
                    relay_db,
                )
            self.assertEqual(inactive.exception.code, "inactive_lease")
            self.assertEqual(inactive.exception.details["state"], "expired")

    def test_remote_legacy_inbox_marks_completeness_unknown(self) -> None:
        from commons import remote

        legacy_messages = [{"message_id": f"msg_{index}", "body": "legacy"} for index in range(200)]
        with mock.patch("commons.remote.request", return_value=legacy_messages):
            result = remote.inbox("default", "demo", "reader", limit=500)
        self.assertEqual(result["page"]["returned_count"], 200)
        self.assertFalse(result["page"]["window_complete"])
        self.assertTrue(result["page"]["legacy_response"])
        self.assertEqual(result["page"]["completeness"], "unknown_legacy")
        self.assertTrue(result["page"]["truncated"])

    def test_remote_project_uses_enrolled_workspace_scope(self) -> None:
        from commons import remote

        with mock.patch(
            "commons.scope.resolve",
            return_value={"mode": "remote", "remote": "work", "project": "workspace-project"},
        ):
            self.assertEqual(remote.project_arg("work", None), "workspace-project")

    def test_remote_token_file_requires_private_permissions(self) -> None:
        from commons import remote

        with tempfile.TemporaryDirectory() as td:
            token_file = Path(td) / "relay.token"
            token_file.write_text("secret-token\n", encoding="utf-8")
            token_file.chmod(0o644)
            with mock.patch.dict(os.environ, {"COMMONS_TEST_TOKEN": ""}):
                with self.assertRaises(remote.RemoteClientError) as raised:
                    remote.token_for(
                        {"token_env": "COMMONS_TEST_TOKEN", "token_file": str(token_file)}
                    )
            self.assertEqual(raised.exception.code, "relay_token_permissions_unsafe")
            self.assertIn("chmod 600", raised.exception.remediation)

            token_file.chmod(0o600)
            with mock.patch.dict(os.environ, {"COMMONS_TEST_TOKEN": ""}):
                self.assertEqual(
                    remote.token_for(
                        {"token_env": "COMMONS_TEST_TOKEN", "token_file": str(token_file)}
                    ),
                    "secret-token",
                )

    def test_relay_inbox_pagination_receipts_and_archive(self) -> None:
        from commons import relay
        from commons import remote

        self.assertEqual(
            relay.canonical_resource_id(" DEPLOY-SLOT:Demo//Staging/ "),
            "deploy-slot:demo/staging",
        )
        self.assertEqual(
            relay.canonical_resource_id("path:repo/./src\\worker.py"),
            "path:repo/src/worker.py",
        )
        with self.assertRaises(relay.RelayError):
            relay.canonical_resource_id("staging")
        with self.assertRaises(relay.RelayError):
            relay.canonical_resource_id("path:repo/../secret")

        with tempfile.TemporaryDirectory() as td:
            relay_db = str(Path(td) / "relay.db")
            register_relay_agent(
                relay, {"project_id": "paging", "agent_id": "sender", "runtime": "codex"}, relay_db
            )
            register_relay_agent(
                relay, {"project_id": "paging", "agent_id": "reader_a", "runtime": "codex"}, relay_db
            )
            register_relay_agent(
                relay, {"project_id": "paging", "agent_id": "reader_b", "runtime": "claude-code"}, relay_db
            )
            with relay.connect(relay_db) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM message_audience").fetchone()[0], 0)
            sent = [
                relay.send_message(
                    {
                        "project_id": "paging",
                        "sender_agent_id": "sender",
                        "recipient": "broadcast",
                        "body": f"message {index:03d}",
                    },
                    relay_db,
                )
                for index in range(205)
            ]

            first = relay.fetch_inbox("paging", "reader_a", limit=500, db=relay_db)
            self.assertEqual(len(first["messages"]), 200)
            self.assertEqual(first["page"]["server_limit"], 200)
            self.assertTrue(first["page"]["truncated"])
            self.assertFalse(first["page"]["window_complete"])
            self.assertIsNotNone(first["page"]["next_cursor"])

            appended_after_cursor = relay.send_message(
                {
                    "project_id": "paging",
                    "sender_agent_id": "sender",
                    "recipient": "broadcast",
                    "body": "newer than the paginated window",
                },
                relay_db,
            )

            second = relay.fetch_inbox(
                "paging",
                "reader_a",
                limit=500,
                cursor=first["page"]["next_cursor"],
                db=relay_db,
            )
            self.assertEqual(len(second["messages"]), 5)
            self.assertTrue(second["page"]["window_complete"])
            all_ids = {message["message_id"] for message in first["messages"] + second["messages"]}
            self.assertEqual(len(all_ids), 205)
            self.assertNotIn(appended_after_cursor["message_id"], all_ids)

            target = sent[-1]
            first_ack = relay.ack_message(target["message_id"], "reader_a", relay_db, "paging")
            second_ack = relay.ack_message(target["message_id"], "reader_a", relay_db, "paging")
            self.assertTrue(first_ack["newly_acked"])
            self.assertFalse(second_ack["newly_acked"])
            reader_a_unread = relay.fetch_inbox("paging", "reader_a", unread_only=True, limit=500, db=relay_db)
            reader_b_unread = relay.fetch_inbox("paging", "reader_b", unread_only=True, limit=500, db=relay_db)
            self.assertNotIn(target["message_id"], {message["message_id"] for message in reader_a_unread["messages"]})
            self.assertIn(target["message_id"], {message["message_id"] for message in reader_b_unread["messages"]})

            archived = relay.get_message("paging", target["message_id"], "reader_a", relay_db)
            self.assertEqual(archived["message_id"], target["message_id"])
            self.assertEqual(archived["receipt_summary"]["acked_count"], 1)
            self.assertFalse(archived["receipt_summary"]["all_acked"])

            register_relay_agent(
                relay, {"project_id": "paging", "agent_id": "late_reader", "runtime": "codex"}, relay_db
            )
            late_inbox = relay.fetch_inbox("paging", "late_reader", limit=500, db=relay_db)
            self.assertEqual(late_inbox["messages"], [])

            page_one = {
                "messages": first["messages"],
                "page": first["page"],
            }
            page_two = {
                "messages": second["messages"],
                "page": second["page"],
            }
            with mock.patch("commons.remote.request", side_effect=[page_one, page_two]) as request_mock:
                aggregate = remote.inbox("default", "paging", "reader_a", limit=500)
            self.assertEqual(aggregate["page"]["returned_count"], 205)
            self.assertEqual(aggregate["page"]["pages_fetched"], 2)
            self.assertTrue(aggregate["page"]["window_complete"])
            self.assertEqual(request_mock.call_count, 2)

    def test_scope_resolve_and_enroll(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            workspace = Path(td) / "project"
            workspace.mkdir()

            unknown = json_stdout(run_cli(home, "scope", "resolve", "--workspace", str(workspace)))
            self.assertEqual(unknown["mode"], "unknown")
            self.assertEqual(unknown["source"], "default")
            self.assertTrue(unknown["needs_user_decision"])
            self.assertFalse((home / "board").exists())

            missing_remote_details = run_cli(
                home,
                "scope",
                "enroll",
                "--workspace",
                str(workspace),
                "--mode",
                "remote",
                check=False,
            )
            self.assertNotEqual(missing_remote_details.returncode, 0)

            local_scope = json_stdout(
                run_cli(home, "scope", "enroll", "--workspace", str(workspace), "--mode", "local", "--scope", "personal")
            )
            self.assertEqual(local_scope["mode"], "local")
            self.assertEqual(local_scope["scope"], "personal")
            self.assertEqual(local_scope["source"], "project")
            self.assertTrue((workspace / ".commons" / "project.toml").exists())

            remote_scope = json_stdout(
                run_cli(
                    home,
                    "scope",
                    "enroll",
                    "--workspace",
                    str(workspace),
                    "--mode",
                    "remote",
                    "--remote",
                    "work",
                    "--project",
                    "commons-team",
                    "--scope",
                    "work",
                )
            )
            self.assertEqual(remote_scope["mode"], "remote")
            self.assertEqual(remote_scope["remote"], "work")
            self.assertEqual(remote_scope["project"], "commons-team")

            disabled_scope = json_stdout(
                run_cli(home, "scope", "enroll", "--workspace", str(workspace), "--mode", "disabled")
            )
            self.assertEqual(disabled_scope["mode"], "disabled")
            self.assertEqual(disabled_scope["scope"], "disabled")

    def test_scope_toml_serialization_round_trips_untrusted_values(self) -> None:
        from commons import scope

        remote = 'work"\\remote\nnext'
        project = 'project"\nmode = "disabled'
        scope_name = "work-测试"
        project_config = tomllib.loads(scope.render_project_config("remote", remote, project, scope_name))
        self.assertEqual(
            project_config["commons"],
            {"mode": "remote", "remote": remote, "project": project, "scope": scope_name},
        )

        match_path = '/tmp/project"\\path\nnext'
        global_config = tomllib.loads(
            scope.append_workspace_rule(
                "",
                {
                    "match_path": match_path,
                    "mode": "disabled",
                    "scope": 'personal"\nmode = "remote',
                },
            )
        )
        self.assertEqual(global_config["workspace_rules"][0]["match_path"], match_path)
        self.assertEqual(global_config["workspace_rules"][0]["mode"], "disabled")
        self.assertEqual(global_config["workspace_rules"][0]["scope"], 'personal"\nmode = "remote')

    def test_scope_global_workspace_rule(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            work_root = Path(td) / "work"
            work_project = work_root / "repo"
            work_project.mkdir(parents=True)

            rule = json_stdout(
                run_cli(
                    home,
                    "scope",
                    "rule",
                    "add",
                    "--match-path",
                    str(work_root / "*"),
                    "--mode",
                    "remote",
                    "--remote",
                    "work",
                    "--project",
                    "commons-team",
                    "--scope",
                    "work",
                )
            )
            self.assertTrue(rule["ok"])

            resolved = json_stdout(run_cli(home, "scope", "resolve", "--workspace", str(work_project)))
            self.assertEqual(resolved["mode"], "remote")
            self.assertEqual(resolved["source"], "global-rule")
            self.assertEqual(resolved["remote"], "work")
            self.assertEqual(resolved["project"], "commons-team")

    def test_golden_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            init = json_stdout(run_cli(home, "init"))
            self.assertTrue(init["ok"])

            agent_a = json_stdout(
                run_cli(home, "agent", "register", "--runtime", "codex", "--name", "codex-a", "--task", "Golden path")
            )
            agent_b = json_stdout(run_cli(home, "agent", "register", "--runtime", "claude-code", "--name", "claude-b"))
            self.assertTrue(agent_a["agent_id"].startswith("agent_"))
            self.assertTrue(agent_b["agent_id"].startswith("agent_"))

            plan = json_stdout(
                run_cli(
                    home,
                    "plan",
                    "publish",
                    "--task",
                    agent_a["task_id"],
                    "--summary",
                    "Acquire fixture staging",
                    "--agent",
                    agent_a["agent_id"],
                )
            )
            self.assertEqual(plan["version"], 1)
            plan_v2 = json_stdout(
                run_cli(
                    home,
                    "plan",
                    "publish",
                    "--task",
                    agent_a["task_id"],
                    "--summary",
                    "Release fixture staging after validation",
                    "--agent",
                    agent_a["agent_id"],
                )
            )
            self.assertEqual(plan_v2["version"], 2)
            plan_diff = json_stdout(
                run_cli(home, "plan", "diff", "--task", agent_a["task_id"], "--from", "1", "--to", "2")
            )
            self.assertIn("Release fixture staging", plan_diff["diff"])

            shown_task = json_stdout(run_cli(home, "task", "show", agent_a["task_id"]))
            self.assertEqual(shown_task["task_id"], agent_a["task_id"])
            blocked = json_stdout(run_cli(home, "task", "block", agent_a["task_id"], "--reason", "Waiting for fixture"))
            self.assertEqual(blocked["status"], "blocked")
            unblocked = json_stdout(run_cli(home, "task", "unblock", agent_a["task_id"], "--summary", "Fixture ready"))
            self.assertEqual(unblocked["status"], "claimed")

            msg = json_stdout(
                run_cli(
                    home,
                    "msg",
                    "send",
                    f"@{agent_a['agent_id']}",
                    "What resource do you need?",
                    "--sender",
                    agent_b["agent_id"],
                    "--task",
                    agent_a["task_id"],
                )
            )
            self.assertTrue(msg["message_id"].startswith("msg_"))
            board_path = Path(json_stdout(run_cli(home, "board", "path"))["board"])
            self.assertTrue((board_path / "messages" / f"{msg['message_id']}.json").exists())
            self.assertTrue((board_path / "inbox" / agent_a["agent_id"] / f"{msg['message_id']}.json").exists())
            read = json_stdout(run_cli(home, "msg", "read", msg["message_id"]))
            self.assertEqual(read["body"], "What resource do you need?")
            self.assertTrue(read["untrusted"])
            reply = json_stdout(run_cli(home, "msg", "reply", msg["message_id"], "env:fixture/staging", "--sender", agent_a["agent_id"]))
            self.assertTrue(reply["message_id"].startswith("msg_"))
            top_inbox = json_stdout(run_cli(home, "inbox", "--agent", agent_b["agent_id"]))
            self.assertGreaterEqual(len(top_inbox), 1)
            message_file = home / "message.md"
            message_file.write_text("File based hello", encoding="utf-8")
            file_msg = json_stdout(
                run_cli(
                    home,
                    "msg",
                    "send",
                    f"@{agent_b['agent_id']}",
                    "--file",
                    str(message_file),
                    "--sender",
                    agent_a["agent_id"],
                )
            )
            self.assertFalse(file_msg["redacted"])
            broadcast = json_stdout(
                run_cli(
                    home,
                    "msg",
                    "broadcast",
                    "--resource",
                    "env:fixture/staging",
                    "Deploy starting",
                    "--sender",
                    agent_a["agent_id"],
                )
            )
            self.assertTrue(broadcast["message_id"].startswith("msg_"))

            context = json_stdout(
                run_cli(
                    home,
                    "context",
                    "publish",
                    "--task",
                    agent_a["task_id"],
                    "--summary",
                    "Current state: ready for staging",
                    "--agent",
                    agent_a["agent_id"],
                )
            )
            self.assertTrue(context["message_id"].startswith("msg_"))
            shown_context = json_stdout(run_cli(home, "context", "show", "--task", agent_a["task_id"]))
            self.assertEqual(len(shown_context), 1)

            artifact_source = home / "safe.log"
            artifact_source.write_text("fixture ok\n", encoding="utf-8")
            artifact = json_stdout(
                run_cli(
                    home,
                    "artifact",
                    "attach",
                    "--task",
                    agent_a["task_id"],
                    "--type",
                    "safe-log",
                    "--path",
                    str(artifact_source),
                )
            )
            artifacts = json_stdout(run_cli(home, "artifact", "list", "--task", agent_a["task_id"]))
            self.assertEqual(artifacts[0]["artifact_id"], artifact["artifact_id"])
            shown_artifact = json_stdout(run_cli(home, "artifact", "show", artifact["artifact_id"]))
            self.assertEqual(shown_artifact["sha256"], artifact["sha256"])

            lease = json_stdout(
                run_cli(
                    home,
                    "lease",
                    "acquire",
                    "env:fixture/staging",
                    "--mode",
                    "write",
                    "--agent",
                    agent_a["agent_id"],
                    "--reason",
                    "test",
                )
            )
            self.assertEqual(lease["fencing_epoch"], 1)
            self.assertTrue((board_path / "leases" / f"{lease['lease_id']}.json").exists())

            denied = run_cli(
                home,
                "lease",
                "acquire",
                "ENV:fixture/staging",
                "--mode",
                "exclusive",
                "--agent",
                agent_b["agent_id"],
                check=False,
            )
            self.assertEqual(denied.returncode, 2)
            denial = json.loads(denied.stdout)
            self.assertIn("lease conflict", denial["error"])
            self.assertEqual(denial["details"]["holder_agent_id"], agent_a["agent_id"])
            local_coordination = shlex.split(denial["details"]["safe_next_actions"][0])
            self.assertEqual(local_coordination[:4], ["commons", "msg", "send", agent_a["agent_id"]])
            coordinated = json_stdout(run_cli(home, *local_coordination[1:]))
            coordinated_inbox = json_stdout(run_cli(home, "inbox", "--agent", agent_a["agent_id"]))
            coordinated_message = next(
                message for message in coordinated_inbox if message["message_id"] == coordinated["message_id"]
            )
            self.assertEqual(coordinated_message["sender_agent_id"], agent_b["agent_id"])

            status = json_stdout(run_cli(home, "status"))
            self.assertEqual(len(status["agents"]), 2)
            self.assertEqual(len(status["active_leases"]), 1)
            watch_once = json_stdout(run_cli(home, "watch", "--once"))
            self.assertEqual(len(watch_once["agents"]), 2)
            resources = json_stdout(run_cli(home, "resource", "list"))
            self.assertGreaterEqual(len(resources), 1)
            resource = json_stdout(run_cli(home, "resource", "show", "env:fixture/staging"))
            self.assertEqual(resource["canonical_id"], "env:fixture/staging")
            sync = json_stdout(run_cli(home, "board", "sync"))
            self.assertGreaterEqual(sync["messages"], 3)
            self.assertTrue((board_path / "status.json").exists())
            task_audit = json_stdout(run_cli(home, "audit", "task", agent_a["task_id"]))
            self.assertGreaterEqual(len(task_audit), 1)
            resource_audit = json_stdout(run_cli(home, "audit", "resource", "env:fixture/staging"))
            self.assertGreaterEqual(len(resource_audit), 1)
            task_export = json_stdout(run_cli(home, "export", "task", agent_a["task_id"]))
            self.assertIn("Commons Task Report", task_export)
            resource_export = json_stdout(run_cli(home, "export", "resource", "env:fixture/staging"))
            self.assertIn("Commons Resource Report", resource_export)
            audit_verify = json_stdout(run_cli(home, "audit", "verify"))
            self.assertTrue(audit_verify["ok"])
            offline = json_stdout(run_cli(home, "agent", "unregister", agent_b["agent_id"]))
            self.assertEqual(offline["status"], "offline")

    def test_wrapped_command_denial_prevents_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            marker = home / "marker"
            run_cli(home, "init")
            agent_a = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "a"))
            agent_b = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "b"))
            run_cli(
                home,
                "lease",
                "acquire",
                "deploy-slot:fixture/staging",
                "--mode",
                "exclusive",
                "--agent",
                agent_a["agent_id"],
            )
            proc = run_cli(
                home,
                "run",
                "--resource",
                "deploy-slot:fixture/staging",
                "--mode",
                "exclusive",
                "--agent",
                agent_b["agent_id"],
                "--",
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')",
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(marker.exists())

    def test_redacts_untrusted_messages_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            run_cli(home, "init")
            agent = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "redaction"))
            msg = json_stdout(
                run_cli(
                    home,
                    "msg",
                    "send",
                    f"@{agent['agent_id']}",
                    "token=supersecret sk-abcdefghijklmnop",
                    "--sender",
                    agent["agent_id"],
                )
            )
            self.assertTrue(msg["redacted"])
            read = json_stdout(run_cli(home, "msg", "read", msg["message_id"]))
            self.assertNotIn("supersecret", read["body"])
            self.assertNotIn("sk-abcdefghijklmnop", read["body"])
            self.assertTrue(read["untrusted"])

            source = home / "secret.log"
            source.write_text("api_key=verysecret\nok=true\n", encoding="utf-8")
            artifact = json_stdout(
                run_cli(home, "artifact", "attach", "--type", "secret-risk", "--path", str(source))
            )
            self.assertTrue(artifact["redacted"])
            self.assertEqual(artifact["visibility"], "human-only")
            stored = Path(artifact["stored_path"]).read_text(encoding="utf-8")
            self.assertNotIn("verysecret", stored)

            symlink = home / "secret-link.log"
            os.symlink(source, symlink)
            rejected_symlink = run_cli(
                home,
                "artifact",
                "attach",
                "--type",
                "safe-log",
                "--path",
                str(symlink),
                check=False,
            )
            self.assertEqual(rejected_symlink.returncode, 1)

            traversal_path = home / ".." / home.name / "secret.log"
            rejected_traversal = run_cli(
                home,
                "artifact",
                "attach",
                "--type",
                "safe-log",
                "--path",
                str(traversal_path),
                check=False,
            )
            self.assertEqual(rejected_traversal.returncode, 1)

    def test_builtin_e2e(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            result = json_stdout(run_cli(home, "test", "e2e", "--scenario", "all", "--agents", "codex,claude-code"))
            self.assertTrue(result["ok"])
            scenarios = {item["scenario"]: item for item in result["results"]}
            self.assertIn("golden-path", scenarios)
            self.assertIn("staging-contention", scenarios)
            self.assertIn("db-migration-handoff", scenarios)
            self.assertIsNotNone(scenarios["golden-path"]["denial"])
            self.assertIsNotNone(scenarios["staging-contention"]["denial"])
            self.assertIsNotNone(scenarios["db-migration-handoff"]["context_message_id"])

    def test_daemon_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            env = {
                "COMMONS_DAEMON_PORT": str(free_port()),
                "HTTP_PROXY": "http://127.0.0.1:1",
                "HTTPS_PROXY": "http://127.0.0.1:1",
                "NO_PROXY": "",
            }
            up = json_stdout(run_cli(home, "up", extra_env=env))
            self.assertTrue(up["ok"])
            status = json_stdout(run_cli(home, "daemon", "status", extra_env=env))
            self.assertTrue(status["http_healthy"])
            logs = json_stdout(run_cli(home, "daemon", "logs", extra_env=env))
            self.assertTrue(logs["ok"])
            stopped = json_stdout(run_cli(home, "daemon", "stop", extra_env=env))
            self.assertTrue(stopped["ok"])

    def test_resource_alias_prevents_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            run_cli(home, "init")
            agent_a = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "a"))
            agent_b = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "b"))
            alias = json_stdout(run_cli(home, "resource", "alias", "add", "staging", "env:fixture/staging"))
            self.assertEqual(alias["canonical_id"], "env:fixture/staging")
            run_cli(home, "lease", "acquire", "env:fixture/staging", "--mode", "write", "--agent", agent_a["agent_id"])
            denied = run_cli(
                home,
                "lease",
                "acquire",
                "staging",
                "--mode",
                "exclusive",
                "--agent",
                agent_b["agent_id"],
                check=False,
            )
            self.assertEqual(denied.returncode, 2)

    def test_renew_rejects_stale_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            run_cli(home, "init")
            agent = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "a"))
            lease = json_stdout(
                run_cli(home, "lease", "acquire", "db:fixture/staging", "--mode", "exclusive", "--agent", agent["agent_id"])
            )
            stale = run_cli(
                home,
                "lease",
                "renew",
                lease["lease_id"],
                "--agent",
                agent["agent_id"],
                "--fencing-epoch",
                str(lease["fencing_epoch"] + 1),
                check=False,
            )
            self.assertEqual(stale.returncode, 2)
            ok = json_stdout(
                run_cli(
                    home,
                    "lease",
                    "renew",
                    lease["lease_id"],
                    "--agent",
                    agent["agent_id"],
                    "--fencing-epoch",
                    str(lease["fencing_epoch"]),
                )
            )
            self.assertTrue(ok["ok"])

    def test_concurrent_conflicting_acquire_has_single_winner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            run_cli(home, "init")
            agent_a = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "a"))
            agent_b = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "b"))

            def acquire(agent_id: str) -> int:
                return run_cli(
                    home,
                    "lease",
                    "acquire",
                    "deploy-slot:fixture/staging",
                    "--mode",
                    "exclusive",
                    "--agent",
                    agent_id,
                    check=False,
                ).returncode

            with ThreadPoolExecutor(max_workers=2) as pool:
                codes = list(pool.map(acquire, [agent_a["agent_id"], agent_b["agent_id"]]))
            self.assertEqual(sorted(codes), [0, 2])

    def test_specialized_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            marker = home / "deploy-marker"
            run_cli(home, "init")
            agent = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "deploy-agent"))
            deploy = json_stdout(
                run_cli(
                    home,
                    "deploy",
                    "staging",
                    "--resource",
                    "deploy-slot:fixture/staging",
                    "--agent",
                    agent["agent_id"],
                    "--",
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(marker)!r}).write_text('ok')",
                )
            )
            self.assertEqual(deploy["exit_code"], 0)
            self.assertEqual(marker.read_text(), "ok")

            browser = json_stdout(
                run_cli(home, "browser", "claim", "fixture/default", "--agent", agent["agent_id"], "--ttl", "1m")
            )
            self.assertEqual(browser["resource_id"], "browser-profile:fixture/default")

    def test_wrapped_command_launch_failure_releases_lease(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            run_cli(home, "init")
            agent = json_stdout(run_cli(home, "agent", "register", "--runtime", "fake", "--name", "runner"))

            failed = run_cli(
                home,
                "run",
                "--resource",
                "server:fixture/missing-command",
                "--agent",
                agent["agent_id"],
                "--",
                "definitely-not-a-real-command",
                check=False,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn("unable to start wrapped command", json_stdout(failed)["error"])

            active = json_stdout(run_cli(home, "lease", "list", "--active"))
            self.assertEqual(active, [])
            leases = json_stdout(run_cli(home, "lease", "list"))
            self.assertEqual(len(leases), 1)
            self.assertEqual(leases[0]["state"], "released")

            with sqlite3.connect(home / "state" / "commons.db") as conn:
                operation = conn.execute(
                    "SELECT state, exit_code FROM operations WHERE resource_id = ?",
                    ("server:fixture/missing-command",),
                ).fetchone()
            self.assertEqual(operation, ("failed", 127))

    def test_skill_install_and_suffix_json_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "commons-home"
            project = Path(td) / "project"
            project.mkdir()
            project = project.resolve()

            doctor = json_stdout(run_cli_raw(home, "doctor", "--json"))
            self.assertTrue(doctor["ok"])
            self.assertIn("cli", doctor)
            self.assertFalse(doctor["cli"]["shim_exists"])
            self.assertEqual(doctor["scope"]["mode"], "unknown")
            self.assertTrue(doctor["user"]["configured"])
            self.assertEqual(doctor["user"]["slug"], "test-user")
            self.assertFalse(doctor["board"]["required"])
            self.assertFalse((home / "board").exists())

            fixed = json_stdout(run_cli_raw(home, "doctor", "--fix", "--json"))
            self.assertTrue(fixed["ok"])
            self.assertTrue(fixed["cli"]["shim_exists"])

            installed = json_stdout(
                run_cli_raw(
                    home,
                    "install-skill",
                    "--target",
                    "all",
                    "--scope",
                    "project",
                    "--project-dir",
                    str(project),
                    "--json",
                )
            )
            self.assertTrue(installed["ok"])
            self.assertRegex(installed["skill_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(installed["cli"]["shim_exists"])
            paths = {item["target"]: Path(item["path"]) for item in installed["installed"]}
            self.assertTrue((paths["codex"] / "SKILL.md").exists())
            self.assertTrue((paths["claude"] / "SKILL.md").exists())
            self.assertTrue((paths["cline"] / "SKILL.md").exists())
            self.assertEqual(paths["codex"], project / ".agents" / "skills" / "commons")
            self.assertEqual(paths["claude"], project / ".claude" / "skills" / "commons")
            self.assertEqual(paths["cline"], project / ".agents" / "skills" / "commons")

            report = json_stdout(run_cli_raw(home, "doctor", "--project-dir", str(project), "--json"))
            self.assertTrue(report["ok"])
            self.assertEqual(report["mode"], "filesystem-first")
            self.assertFalse(report["mcp_required"])
            self.assertFalse(report["daemon"]["required"])
            self.assertTrue(report["board"]["subdirs"]["messages"])
            self.assertTrue(report["cli"]["shim_exists"])
            self.assertTrue(report["skills"]["codex"]["project_installed"])
            self.assertTrue(report["skills"]["claude"]["project_installed"])
            self.assertTrue(report["skills"]["cline"]["project_installed"])
            self.assertTrue(report["skills"]["codex"]["project_up_to_date"])
            self.assertTrue(report["skills"]["claude"]["project_up_to_date"])
            self.assertTrue(report["skills"]["cline"]["project_up_to_date"])
            self.assertTrue(report["skills"]["cline"]["rule"]["project_installed"])
            self.assertTrue(report["skills"]["cline"]["rule"]["project_up_to_date"])
            self.assertIn("cline", report["runtimes"])

            (paths["codex"] / "SKILL.md").write_text("outdated\n", encoding="utf-8")
            stale_report = json_stdout(run_cli_raw(home, "doctor", "--project-dir", str(project), "--json"))
            self.assertFalse(stale_report["skills"]["codex"]["project_up_to_date"])
            self.assertTrue(any("codex project Commons skill is outdated" in item for item in stale_report["warnings"]))

    def test_global_skill_install_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            commons_home = Path(td) / "commons-home"
            fake_home = Path(td) / "user-home"
            fake_home.mkdir()
            installed = json_stdout(
                run_cli_raw(
                    commons_home,
                    "install-skill",
                    "--target",
                    "all",
                    "--scope",
                    "user",
                    "--json",
                    extra_env={"HOME": str(fake_home)},
                )
            )
            self.assertRegex(installed["skill_sha256"], r"^[0-9a-f]{64}$")
            paths = {item["target"]: Path(item["path"]) for item in installed["installed"]}
            shim = Path(installed["cli"]["shim_path"])
            self.assertEqual(paths["codex"], fake_home / ".agents" / "skills" / "commons")
            self.assertEqual(paths["claude"], fake_home / ".claude" / "skills" / "commons")
            self.assertEqual(paths["cline"], fake_home / ".agents" / "skills" / "commons")
            self.assertTrue((paths["codex"] / "SKILL.md").exists())
            self.assertTrue((paths["claude"] / "SKILL.md").exists())
            self.assertTrue((paths["cline"] / "SKILL.md").exists())
            cline_install = next(item for item in installed["installed"] if item["target"] == "cline")
            cline_rule = Path(cline_install["rule_path"])
            self.assertEqual(cline_rule, fake_home / ".cline" / "rules" / "commons-bootstrap.md")
            self.assertTrue(cline_rule.exists())
            self.assertIn("COMMONS_AGENT_RUNTIME=cline", cline_rule.read_text(encoding="utf-8"))
            installed_skill = (paths["codex"] / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("scope-first", installed_skill)
            self.assertIn("pipx install agent-commons==0.5.0", installed_skill)
            self.assertIn("commons install-skill --target all --scope user", installed_skill)
            self.assertIn("Commons 0.5.0 or newer is required", installed_skill)
            self.assertIn("Cline", installed_skill)
            self.assertIn("COMMONS_AGENT_RUNTIME", installed_skill)
            self.assertIn("contact_code", installed_skill)
            self.assertIn("Commons scope", installed_skill)
            self.assertIn("scope resolve", installed_skill)
            self.assertLess(
                installed_skill.index('scope resolve --workspace "$PWD"'),
                installed_skill.index('if [ -z "${COMMONS_AGENT_RUNTIME:-}" ]'),
            )
            self.assertIn("commons user set", installed_skill)
            self.assertIn("Never infer the human name", installed_skill)
            self.assertIn("remote msg broadcast", installed_skill)
            self.assertNotIn("--runtime auto", installed_skill)
            self.assertNotIn("python3 -m commons.cli doctor --fix", installed_skill)
            self.assertFalse((commons_home / "board").exists())
            self.assertTrue(shim.exists())
            self.assertTrue(os.access(shim, os.X_OK))

            env = os.environ.copy()
            env["COMMONS_HOME"] = str(commons_home)
            env["HOME"] = str(fake_home)
            env.pop("PYTHONPATH", None)
            shim_doctor = subprocess.run(
                [str(shim), "doctor", "--json"],
                cwd="/",
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(shim_doctor.returncode, 0, shim_doctor.stderr)
            shim_report = json.loads(shim_doctor.stdout)
            self.assertTrue(shim_report["cli"]["shim_exists"])
            self.assertTrue(shim_report["skills"]["cline"]["rule"]["user_up_to_date"])

            legacy_codex = fake_home / ".codex" / "skills" / "commons"
            legacy_codex.mkdir(parents=True)
            (legacy_codex / "SKILL.md").write_text(installed_skill, encoding="utf-8")
            duplicate_report = json_stdout(
                run_cli_raw(commons_home, "doctor", "--json", extra_env={"HOME": str(fake_home)})
            )
            self.assertEqual(
                duplicate_report["skills"]["codex"]["duplicate_paths"],
                [str(legacy_codex)],
            )
            self.assertTrue(any("active from multiple paths" in item for item in duplicate_report["warnings"]))

    def test_both_skill_target_remains_codex_and_claude_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            commons_home = Path(td) / "commons-home"
            project = Path(td) / "project"
            project.mkdir()

            installed = json_stdout(
                run_cli_raw(
                    commons_home,
                    "install-skill",
                    "--target",
                    "both",
                    "--scope",
                    "project",
                    "--project-dir",
                    str(project),
                    "--json",
                )
            )

            self.assertEqual([item["target"] for item in installed["installed"]], ["codex", "claude"])
            self.assertFalse((project / ".cline" / "skills" / "commons").exists())

    def test_codex_only_install_does_not_require_cline_rule_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            commons_home = Path(td) / "commons-home"
            fake_home = Path(td) / "user-home"
            project = Path(td) / "project"
            project.mkdir()
            extra_env = {"HOME": str(fake_home), "PATH": ""}

            run_cli_raw(
                commons_home,
                "install-skill",
                "--target",
                "codex",
                "--scope",
                "user",
                "--json",
                extra_env=extra_env,
            )
            report = json_stdout(
                run_cli_raw(
                    commons_home,
                    "doctor",
                    "--project-dir",
                    str(project),
                    "--json",
                    extra_env=extra_env,
                )
            )

            self.assertTrue(report["skills"]["codex"]["user_installed"])
            self.assertTrue(report["skills"]["cline"]["user_installed"])
            self.assertFalse(report["runtimes"]["cline"]["available"])
            self.assertFalse(
                any("Cline bootstrap rule" in warning for warning in report["warnings"]),
                report["warnings"],
            )

    def test_runtime_resolution_supports_cline_and_never_persists_auto(self) -> None:
        from commons import service

        self.assertEqual(service.resolve_runtime("cline-cli"), "cline")
        self.assertEqual(service.resolve_runtime("claude"), "claude-code")
        self.assertEqual(service.resolve_runtime("codex-cli"), "codex")

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(service.resolve_runtime("auto"), "custom")
        with mock.patch.dict(os.environ, {"COMMONS_AGENT_RUNTIME": "cline"}, clear=True):
            self.assertEqual(service.resolve_runtime("auto"), "cline")
        with mock.patch.dict(os.environ, {"CLINE_SESSION_ID": "session-test"}, clear=True):
            self.assertEqual(service.resolve_runtime("auto"), "cline")

    def test_cli_shim_stays_inside_virtual_environment(self) -> None:
        from commons import service

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            commons_home = root / "commons-home"
            venv_python = root / "venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.symlink_to(Path(sys.executable))

            with mock.patch.dict(os.environ, {"COMMONS_HOME": str(commons_home)}):
                with mock.patch.object(service.sys, "executable", str(venv_python)):
                    installed = service.install_cli_shim()

            shim = Path(installed["path"])
            shim_text = shim.read_text(encoding="utf-8")
            self.assertEqual(installed["python"], str(venv_python.absolute()))
            self.assertIn(f"COMMONS_PYTHON={venv_python.absolute()}", shim_text)
            self.assertNotIn(f"COMMONS_PYTHON={Path(sys.executable).resolve()}\n", shim_text)
            self.assertLess(
                shim_text.index('if [ -f "$COMMONS_SOURCE/commons/cli.py" ]'),
                shim_text.index("if \"$COMMONS_PYTHON\" -c 'import commons.cli'"),
            )

    def test_installer_loads_packaged_cli_from_neutral_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            commons_home = root / "commons-home"
            fake_python = commons_home / "venv" / "bin" / "python"
            fake_python.parent.mkdir(parents=True)
            call_log = root / "python-calls.log"
            fake_python.write_text(
                "#!/bin/sh\n"
                "printf 'PWD=%s|' \"$PWD\" >> \"$COMMONS_FAKE_PYTHON_LOG\"\n"
                "printf '<%s>' \"$@\" >> \"$COMMONS_FAKE_PYTHON_LOG\"\n"
                "printf '\\n' >> \"$COMMONS_FAKE_PYTHON_LOG\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["COMMONS_FAKE_PYTHON_LOG"] = str(call_log)
            installed = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts" / "install.sh"),
                    "--source",
                    ".",
                    "--commons-home",
                    str(commons_home),
                    "--python",
                    sys.executable,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            calls = call_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].startswith(f"PWD={commons_home.resolve()}|"))
            self.assertIn("<-I><-m><pip><install>", calls[0])
            self.assertIn(f"<{ROOT.resolve()}>", calls[0])
            self.assertTrue(calls[1].startswith(f"PWD={commons_home.resolve()}|"))
            self.assertIn("<-I><-m><commons.cli><install-skill>", calls[1])
            self.assertIn("<--target><both>", calls[1])

    def test_runtime_smoke_prepare_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "commons-home"
            project = Path(td) / "project"
            project.mkdir()
            prepared = json_stdout(
                run_cli(
                    home,
                    "test",
                    "runtime",
                    "prepare",
                    "--agents",
                    "codex,cline",
                    "--project-dir",
                    str(project),
                )
            )
            self.assertTrue(Path(prepared["prompt_paths"]["agent_a"]).exists())
            self.assertTrue(Path(prepared["prompt_paths"]["agent_b"]).exists())
            self.assertIn(
                "commons agent register --runtime cline",
                Path(prepared["prompt_paths"]["agent_b"]).read_text(encoding="utf-8"),
            )

            run_id = prepared["run_id"]
            resource = prepared["resource_id"]
            agent_a_name = prepared["agents"][0]["name"]
            agent_b_name = prepared["agents"][1]["name"]
            agent_a = json_stdout(
                run_cli(
                    home,
                    "agent",
                    "register",
                    "--runtime",
                    "codex",
                    "--workspace",
                    str(project),
                    "--name",
                    agent_a_name,
                    "--task",
                    f"Runtime smoke {run_id}",
                )
            )
            agent_b = json_stdout(
                run_cli(
                    home,
                    "agent",
                    "register",
                    "--runtime",
                    "cline",
                    "--workspace",
                    str(project),
                    "--name",
                    agent_b_name,
                    "--task",
                    f"Runtime smoke {run_id} Agent B",
                )
            )
            run_cli(
                home,
                "plan",
                "publish",
                "--task",
                agent_a["task_id"],
                "--agent",
                agent_a["agent_id"],
                "--summary",
                f"Runtime smoke {run_id}: Agent A holds {resource}.",
            )
            run_cli(
                home,
                "plan",
                "publish",
                "--task",
                agent_b["task_id"],
                "--agent",
                agent_b["agent_id"],
                "--summary",
                f"Runtime smoke {run_id}: Agent B coordinates for {resource}.",
            )
            lease = json_stdout(
                run_cli(
                    home,
                    "lease",
                    "acquire",
                    resource,
                    "--mode",
                    "write",
                    "--agent",
                    agent_a["agent_id"],
                    "--reason",
                    f"Runtime smoke {run_id}",
                )
            )
            denied = run_cli(
                home,
                "lease",
                "acquire",
                resource,
                "--mode",
                "exclusive",
                "--agent",
                agent_b["agent_id"],
                "--reason",
                f"Runtime smoke {run_id}",
                check=False,
            )
            self.assertEqual(denied.returncode, 2)
            run_cli(
                home,
                "msg",
                "send",
                "@broadcast",
                f"Runtime smoke {run_id}: Agent A holds {resource}.",
                "--sender",
                agent_a["agent_id"],
                "--task",
                agent_a["task_id"],
            )
            run_cli(
                home,
                "msg",
                "send",
                f"@{agent_a['agent_id']}",
                f"Runtime smoke {run_id}: Agent B saw the {resource} denial.",
                "--sender",
                agent_b["agent_id"],
                "--task",
                agent_b["task_id"],
            )
            run_cli(
                home,
                "lease",
                "release",
                lease["lease_id"],
                "--agent",
                agent_a["agent_id"],
                "--fencing-epoch",
                str(lease["fencing_epoch"]),
            )

            verified = json_stdout(run_cli(home, "test", "runtime", "verify", run_id))
            self.assertTrue(verified["ok"])
            self.assertTrue(verified["checks"]["lease_denial_recorded"])

    def test_relay_remote_cli_e2e(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "commons-home"
            relay_db = root / "relay.db"
            port = free_port()
            url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            env["COMMONS_RELAY_TOKEN"] = "test-token"
            env["COMMONS_CONSOLE_TOKEN"] = "console-test-token"
            env["COMMONS_WORKSPACE_NAME"] = "Test Workspace"
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "commons.cli",
                    "relay",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--db",
                    str(relay_db),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(50):
                    try:
                        with local_urlopen(f"{url}/health", timeout=0.2) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    proc.terminate()
                    try:
                        stdout, stderr = proc.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        stdout, stderr = proc.communicate(timeout=5)
                    raise AssertionError(f"relay did not start\nstdout={stdout}\nstderr={stderr}")

                no_auth = urllib.request.Request(f"{url}/v1/agents?project_id=demo")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    local_urlopen(no_auth, timeout=1)
                self.assertEqual(raised.exception.code, 401)

                oversized_connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                oversized_connection.putrequest("POST", "/v1/console/session")
                oversized_connection.putheader("Content-Type", "application/json")
                oversized_connection.putheader("Content-Length", str(1024 * 1024 + 1))
                oversized_connection.endheaders()
                oversized_response = oversized_connection.getresponse()
                self.assertEqual(oversized_response.status, 413)
                oversized_error = json.loads(oversized_response.read().decode("utf-8"))
                oversized_connection.close()
                self.assertEqual(oversized_error["error_code"], "request_body_too_large")

                invalid_limit = urllib.request.Request(
                    f"{url}/v1/inbox?project_id=demo&agent_id=agent_header&limit=abc",
                    headers={"Authorization": "Bearer test-token"},
                )
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    local_urlopen(invalid_limit, timeout=1)
                self.assertEqual(raised.exception.code, 400)
                invalid_limit_error = json.loads(raised.exception.read().decode("utf-8"))
                self.assertEqual(invalid_limit_error["error_code"], "invalid_query_parameter")

                missing_project = urllib.request.Request(
                    f"{url}/v1/agents/register",
                    data=json.dumps({"agent_id": "agent_missing_project", "runtime": "codex"}).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    local_urlopen(missing_project, timeout=1)
                self.assertEqual(raised.exception.code, 400)
                missing_project_error = json.loads(raised.exception.read().decode("utf-8"))
                self.assertEqual(missing_project_error["error_code"], "project_context_required")
                self.assertEqual(missing_project_error["error_source"], "commons-relay")
                self.assertIn("--project", missing_project_error["remediation"])

                header_project = urllib.request.Request(
                    f"{url}/v1/agents/register",
                    data=json.dumps(
                        {
                            "agent_id": "agent_header",
                            "runtime": "codex",
                            "handle": "test-user-codex-header",
                            "user_name": "Test User",
                        }
                    ).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/json",
                        "X-Commons-Project": "demo",
                    },
                    method="POST",
                )
                with local_urlopen(header_project, timeout=1) as response:
                    header_agent = json.loads(response.read().decode("utf-8"))
                self.assertEqual(header_agent["project_id"], "demo")

                mismatched_project = urllib.request.Request(
                    f"{url}/v1/agents/register",
                    data=json.dumps({"project_id": "other", "agent_id": "agent_mismatch", "runtime": "codex"}).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/json",
                        "X-Commons-Project": "demo",
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    local_urlopen(mismatched_project, timeout=1)
                mismatch_error = json.loads(raised.exception.read().decode("utf-8"))
                self.assertEqual(mismatch_error["error_code"], "project_context_mismatch")

                extra_env = {
                    "COMMONS_RELAY_TOKEN": "test-token",
                    "HTTP_PROXY": "http://127.0.0.1:1",
                    "HTTPS_PROXY": "http://127.0.0.1:1",
                    "NO_PROXY": "",
                }
                added = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "add",
                        "default",
                        "--url",
                        url,
                        "--token-env",
                        "COMMONS_RELAY_TOKEN",
                        "--project",
                        "demo",
                        extra_env=extra_env,
                    )
                )
                self.assertTrue(added["ok"])
                status = json_stdout(run_cli(home, "remote", "status", extra_env=extra_env))
                self.assertTrue(status["ok"])
                self.assertTrue(status["auth_ready"])
                self.assertEqual(status["project"], "demo")
                self.assertEqual(status["authenticated"]["protocol_version"], 1)
                self.assertEqual(status["authenticated"]["security_model"]["authentication"], "shared_bearer_token")
                self.assertFalse(status["authenticated"]["security_model"]["actor_bound"])

                json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "add",
                        "wrong-token",
                        "--url",
                        url,
                        "--token-env",
                        "COMMONS_WRONG_TOKEN",
                        "--project",
                        "demo",
                        extra_env=extra_env,
                    )
                )
                wrong_status = run_cli(
                    home,
                    "remote",
                    "status",
                    "--remote",
                    "wrong-token",
                    check=False,
                    extra_env={"COMMONS_WRONG_TOKEN": "wrong-token"},
                )
                self.assertEqual(wrong_status.returncode, 1)
                self.assertEqual(json_stdout(wrong_status)["error_code"], "relay_unauthorized")

                token_file = root / "relay.token"
                token_file.write_text("test-token\n", encoding="utf-8")
                token_file.chmod(0o600)
                added_file_remote = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "add",
                        "file",
                        "--url",
                        url,
                        "--token-file",
                        str(token_file),
                        "--project",
                        "demo",
                    )
                )
                self.assertTrue(added_file_remote["ok"])
                file_status = json_stdout(run_cli(home, "remote", "status", "--remote", "file"))
                self.assertTrue(file_status["ok"])
                self.assertTrue(file_status["auth_ready"])
                self.assertEqual(file_status["project"], "demo")

                json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "add",
                        "nodefault",
                        "--url",
                        url,
                        "--token-env",
                        "COMMONS_RELAY_TOKEN",
                        extra_env=extra_env,
                    )
                )
                missing_cli_project = run_cli(
                    home,
                    "remote",
                    "agent",
                    "list",
                    "--remote",
                    "nodefault",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(missing_cli_project.returncode, 1)
                missing_cli_error = json_stdout(missing_cli_project)
                self.assertEqual(missing_cli_error["error_code"], "project_context_required")
                self.assertEqual(missing_cli_error["error_source"], "commons-client")
                self.assertIn("--project", missing_cli_error["remediation"])

                agent_a = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "agent",
                        "register",
                        "--agent",
                        "agent_a",
                        "--runtime",
                        "codex",
                        "--handle",
                        "codex-alpha",
                        "--contact-code",
                        "C7DX92",
                        "--name",
                        "codex-a",
                        "--workspace",
                        "/private/work/secret-repo",
                        "--device-name",
                        "test-mac-studio",
                        extra_env=extra_env,
                    )
                )
                agent_b = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "agent",
                        "register",
                        "--agent",
                        "agent_b",
                        "--runtime",
                        "claude-code",
                        "--handle",
                        "claude-beta",
                        "--name",
                        "claude-b",
                        extra_env=extra_env,
                    )
                )
                cline_env = {**extra_env, "COMMONS_AGENT_RUNTIME": "cline"}
                agent_c = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "agent",
                        "register",
                        "--agent",
                        "agent_c",
                        "--runtime",
                        "auto",
                        "--handle",
                        "cline-gamma",
                        "--name",
                        "cline-c",
                        extra_env=cline_env,
                    )
                )
                self.assertEqual(agent_a["agent_id"], "agent_a")
                self.assertEqual(agent_b["agent_id"], "agent_b")
                self.assertEqual(agent_c["agent_id"], "agent_c")
                self.assertEqual(agent_a["handle"], "test-user-codex-alpha")
                self.assertEqual(agent_b["handle"], "test-user-claude-beta")
                self.assertEqual(agent_c["handle"], "test-user-cline-gamma")
                self.assertEqual(agent_c["runtime"], "cline")
                self.assertEqual(agent_a["contact_code"], "C7DX92")
                self.assertEqual(agent_a["workspace"], "secret-repo")
                self.assertEqual(agent_a["host"], "test-mac-studio")
                self.assertTrue(agent_a["workspace_path_redacted"])
                self.assertRegex(agent_b["contact_code"], r"^[2-9A-Z]{6}$")

                duplicate_handle = run_cli(
                    home,
                    "remote",
                    "agent",
                    "register",
                    "--agent",
                    "agent_handle_collision",
                    "--runtime",
                    "codex",
                    "--handle",
                    "codex-alpha",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(duplicate_handle.returncode, 2)
                duplicate_handle_error = json_stdout(duplicate_handle)
                self.assertEqual(duplicate_handle_error["error_code"], "agent_handle_conflict")
                self.assertTrue(duplicate_handle_error["details"]["suggested_handles"])
                duplicate_code = run_cli(
                    home,
                    "remote",
                    "agent",
                    "register",
                    "--agent",
                    "agent_code_collision",
                    "--runtime",
                    "codex",
                    "--contact-code",
                    "C7DX92",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(duplicate_code.returncode, 2)

                file_remote_agent = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "agent",
                        "register",
                        "--remote",
                        "file",
                        "--agent",
                        "agent_file",
                        "--runtime",
                        "codex",
                    )
                )
                self.assertEqual(file_remote_agent["agent_id"], "agent_file")

                agents = json_stdout(run_cli(home, "remote", "agent", "list", extra_env=extra_env))
                self.assertEqual(
                    {item["agent_id"] for item in agents},
                    {"agent_a", "agent_b", "agent_c", "agent_file", "agent_header"},
                )
                self.assertTrue(all(item["presence"] == "online" for item in agents))
                heartbeat = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "agent",
                        "heartbeat",
                        "--agent",
                        "agent_a",
                        "--status",
                        "busy",
                        extra_env=extra_env,
                    )
                )
                self.assertEqual(heartbeat["status"], "busy")
                self.assertEqual(heartbeat["presence"], "online")

                task = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "task",
                        "create",
                        "Build the Commons Console",
                        "--owner",
                        "agent_a",
                        "--summary",
                        "Expose shared coordination state.",
                        "--current-step",
                        "Implement relay APIs",
                        "--next-step",
                        "Build the frontend",
                        "--progress",
                        "20",
                        extra_env=extra_env,
                    )
                )
                self.assertEqual(task["status"], "in_progress")
                self.assertEqual(task["progress_percent"], 20)
                self.assertEqual(task["owner"]["handle"], "test-user-codex-alpha")
                updated_task = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "task",
                        "update",
                        task["task_id"],
                        "--status",
                        "ready_for_review",
                        "--current-step",
                        "Review the Console",
                        "--next-step",
                        "Deploy production",
                        "--progress",
                        "80",
                        "--expected-version",
                        str(task["version"]),
                        extra_env=extra_env,
                    )
                )
                self.assertEqual(updated_task["version"], 2)
                self.assertEqual(updated_task["progress_percent"], 80)
                listed_tasks = json_stdout(run_cli(home, "remote", "task", "list", extra_env=extra_env))
                self.assertEqual([item["task_id"] for item in listed_tasks], [task["task_id"]])
                shown_task = json_stdout(
                    run_cli(home, "remote", "task", "show", task["task_id"], extra_env=extra_env)
                )
                self.assertEqual(shown_task["status"], "ready_for_review")

                msg = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "msg",
                        "send",
                        "@test-user-claude-beta",
                        "hello from remote relay",
                        "--sender",
                        "agent_a",
                        "--thread",
                        "thread_demo",
                        extra_env=extra_env,
                    )
                )
                agents_after_message = json_stdout(run_cli(home, "remote", "agent", "list", extra_env=extra_env))
                agent_a_after_message = next(item for item in agents_after_message if item["agent_id"] == "agent_a")
                self.assertEqual(agent_a_after_message["status"], "busy")
                inbox = json_stdout(
                    run_cli(home, "remote", "inbox", "--agent", "agent_b", "--unread-only", extra_env=extra_env)
                )
                self.assertEqual(inbox["messages"][0]["message_id"], msg["message_id"])
                self.assertEqual(inbox["messages"][0]["recipient_agent_id"], "agent_b")
                self.assertTrue(inbox["page"]["window_complete"])
                legacy_inbox_request = urllib.request.Request(
                    f"{url}/v1/inbox?project_id=demo&agent_id=agent_b&unread_only=true&limit=50",
                    headers={"Authorization": "Bearer test-token"},
                )
                with local_urlopen(legacy_inbox_request, timeout=1) as response:
                    legacy_inbox = json.loads(response.read().decode("utf-8"))
                self.assertIsInstance(legacy_inbox, list)
                ack = json_stdout(
                    run_cli(home, "remote", "msg", "ack", msg["message_id"], "--agent", "agent_b", extra_env=extra_env)
                )
                self.assertTrue(ack["ok"])
                archived_message = json_stdout(
                    run_cli(home, "remote", "msg", "get", msg["message_id"], "--agent", "agent_b", extra_env=extra_env)
                )
                self.assertEqual(archived_message["message_id"], msg["message_id"])
                self.assertEqual(archived_message["receipt_summary"]["acked_count"], 1)

                code_msg = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "msg",
                        "send",
                        agent_a["contact_code"],
                        "hello by contact code",
                        "--sender",
                        "agent_b",
                        extra_env=extra_env,
                    )
                )
                code_inbox = json_stdout(run_cli(home, "remote", "inbox", "--agent", "agent_a", "--unread-only", extra_env=extra_env))
                self.assertEqual(code_inbox["messages"][0]["message_id"], code_msg["message_id"])

                broadcast = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "msg",
                        "broadcast",
                        "remote broadcast plan",
                        "--sender",
                        "agent_a",
                        "--type",
                        "plan",
                        extra_env=extra_env,
                    )
                )
                broadcast_inbox = json_stdout(run_cli(home, "remote", "inbox", "--agent", "agent_b", "--unread-only", extra_env=extra_env))
                self.assertTrue(any(item["message_id"] == broadcast["message_id"] for item in broadcast_inbox["messages"]))
                sender_ack = run_cli(
                    home,
                    "remote",
                    "msg",
                    "ack",
                    broadcast["message_id"],
                    "--agent",
                    "agent_a",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(sender_ack.returncode, 2)
                items_only = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "inbox",
                        "--agent",
                        "agent_b",
                        "--items-only",
                        extra_env=extra_env,
                    )
                )
                self.assertIsInstance(items_only, list)

                from commons import relay as relay_module

                register_relay_agent(
                    relay_module,
                    {"project_id": "paging-http", "agent_id": "paging_sender", "runtime": "codex"},
                    str(relay_db),
                )
                register_relay_agent(
                    relay_module,
                    {"project_id": "paging-http", "agent_id": "paging_reader", "runtime": "claude-code"},
                    str(relay_db),
                )
                with relay_module.connect(str(relay_db)) as conn, relay_module.transaction(conn):
                    for index in range(205):
                        message_id = f"msg_http_{index:03d}"
                        conn.execute(
                            """
                            INSERT INTO messages(
                              message_id, project_id, thread_id, sender_agent_id,
                              recipient_agent_id, message_type, body, created_at
                            ) VALUES(?, 'paging-http', 'thread_http', 'paging_sender', NULL, 'note', ?, '2026-01-01T00:00:00Z')
                            """,
                            (message_id, f"http page {index}"),
                        )
                        conn.execute(
                            "INSERT INTO message_audience(message_id, agent_id, delivered_at) VALUES(?, 'paging_reader', '2026-01-01T00:00:00Z')",
                            (message_id,),
                        )
                http_pages = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "inbox",
                        "--project",
                        "paging-http",
                        "--agent",
                        "paging_reader",
                        "--limit",
                        "500",
                        extra_env=extra_env,
                    )
                )
                self.assertEqual(http_pages["page"]["returned_count"], 205)
                self.assertEqual(http_pages["page"]["pages_fetched"], 2)
                self.assertTrue(http_pages["page"]["window_complete"])

                lease_a = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "lease",
                        "acquire",
                        "deploy-slot:demo/staging",
                        "--mode",
                        "exclusive",
                        "--agent",
                        "agent_a",
                        "--ttl",
                        "1m",
                        extra_env=extra_env,
                    )
                )
                same_holder = run_cli(
                    home,
                    "remote",
                    "lease",
                    "acquire",
                    "DEPLOY-SLOT:demo//staging/",
                    "--mode",
                    "exclusive",
                    "--agent",
                    "agent_a",
                    "--ttl",
                    "2m",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(same_holder.returncode, 2)
                same_holder_error = json_stdout(same_holder)
                self.assertEqual(same_holder_error["error_code"], "lease_already_held")
                self.assertTrue(same_holder_error["details"]["same_holder"])
                renew_action = shlex.split(same_holder_error["details"]["safe_next_actions"][0])
                self.assertEqual(renew_action[:4], ["commons", "remote", "lease", "renew"])

                missing_renew_epoch = run_cli(
                    home,
                    "remote",
                    "lease",
                    "renew",
                    lease_a["lease_id"],
                    "--agent",
                    "agent_a",
                    "--ttl",
                    "2m",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(missing_renew_epoch.returncode, 1)
                missing_renew_error = json_stdout(missing_renew_epoch)
                self.assertEqual(missing_renew_error["error_code"], "fencing_epoch_required")
                self.assertIn("lease list", missing_renew_error["remediation"])

                renewed = json_stdout(run_cli(home, *renew_action[1:], extra_env=extra_env))
                self.assertEqual(renewed["lease_id"], lease_a["lease_id"])
                self.assertEqual(renewed["fencing_epoch"], lease_a["fencing_epoch"])
                self.assertGreater(renewed["expires_at"], lease_a["expires_at"])
                self.assertEqual(renewed["ttl_seconds"], 120)

                denied = run_cli(
                    home,
                    "remote",
                    "lease",
                    "acquire",
                    "DEPLOY-SLOT:demo//staging/",
                    "--remote",
                    "file",
                    "--mode",
                    "exclusive",
                    "--agent",
                    "agent_b",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(denied.returncode, 2)
                denial = json.loads(denied.stdout)
                self.assertEqual(denial["error_code"], "lease_conflict")
                self.assertEqual(denial["details"]["holder_agent_id"], "agent_a")
                self.assertEqual(denial["details"]["holder_handle"], "test-user-codex-alpha")
                self.assertEqual(denial["details"]["holder_contact_code"], "C7DX92")
                self.assertEqual(denial["details"]["coordination_recipient"], "@test-user-codex-alpha")
                self.assertEqual(denial["details"]["resource_id"], "DEPLOY-SLOT:demo//staging/")
                remote_coordination = shlex.split(denial["details"]["safe_next_actions"][0])
                self.assertIn("file", remote_coordination)
                self.assertIn("demo", remote_coordination)
                self.assertIn("agent_b", remote_coordination)
                coordinated = json_stdout(run_cli(home, *remote_coordination[1:]))
                coordinated_inbox = json_stdout(
                    run_cli(home, "remote", "inbox", "--remote", "file", "--agent", "agent_a")
                )
                self.assertEqual(coordinated_inbox["messages"][0]["message_id"], coordinated["message_id"])
                invalid_resource = run_cli(
                    home,
                    "remote",
                    "lease",
                    "acquire",
                    "staging",
                    "--agent",
                    "agent_b",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(invalid_resource.returncode, 1)
                invalid_resource_error = json_stdout(invalid_resource)
                self.assertEqual(invalid_resource_error["error_code"], "invalid_resource_id")
                missing_release_epoch = run_cli(
                    home,
                    "remote",
                    "lease",
                    "release",
                    lease_a["lease_id"],
                    "--agent",
                    "agent_a",
                    check=False,
                    extra_env=extra_env,
                )
                self.assertEqual(missing_release_epoch.returncode, 1)
                missing_release_error = json_stdout(missing_release_epoch)
                self.assertEqual(missing_release_error["error_code"], "fencing_epoch_required")
                self.assertIn("stale holder", missing_release_error["remediation"])
                released = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "lease",
                        "release",
                        lease_a["lease_id"],
                        "--agent",
                        "agent_a",
                        "--fencing-epoch",
                        str(lease_a["fencing_epoch"]),
                        extra_env=extra_env,
                    )
                )
                self.assertTrue(released["ok"])
                lease_b = json_stdout(
                    run_cli(
                        home,
                        "remote",
                        "lease",
                        "acquire",
                        "deploy-slot:demo/staging",
                        "--mode",
                        "exclusive",
                        "--agent",
                        "agent_b",
                        "--ttl",
                        "1m",
                        extra_env=extra_env,
                    )
                )
                self.assertEqual(lease_b["holder_agent_id"], "agent_b")

                unauthorized_console = urllib.request.Request(f"{url}/v1/console/overview")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    local_urlopen(unauthorized_console, timeout=1)
                self.assertEqual(raised.exception.code, 401)

                login = urllib.request.Request(
                    f"{url}/v1/console/session",
                    data=json.dumps({"token": "console-test-token"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with local_urlopen(login, timeout=1) as response:
                    login_payload = json.loads(response.read().decode("utf-8"))
                    session_cookie = response.headers["Set-Cookie"].split(";", 1)[0]
                self.assertTrue(login_payload["ok"])
                self.assertNotIn("console-test-token", session_cookie)

                console_headers = {"Cookie": session_cookie}
                overview_request = urllib.request.Request(f"{url}/v1/console/overview", headers=console_headers)
                with local_urlopen(overview_request, timeout=1) as response:
                    overview = json.loads(response.read().decode("utf-8"))
                self.assertEqual(overview["workspace"]["name"], "Test Workspace")
                self.assertTrue(any(project["project_id"] == "demo" for project in overview["projects"]))
                demo_summary = next(project for project in overview["projects"] if project["project_id"] == "demo")
                self.assertEqual(demo_summary["active_agent_count"], demo_summary["online_agent_count"])
                self.assertGreaterEqual(demo_summary["broadcast_count"], 1)
                self.assertGreaterEqual(demo_summary["direct_message_count"], 2)
                self.assertEqual(overview["totals"]["registered_agents"], overview["totals"]["agents"])
                self.assertGreaterEqual(overview["totals"]["active_agents"], demo_summary["active_agent_count"])
                self.assertTrue(overview["recent_broadcasts"])
                self.assertTrue(all(message["recipient_agent_id"] is None for message in overview["recent_broadcasts"]))
                self.assertTrue(all(message["project_display_name"] for message in overview["recent_broadcasts"]))

                village_request = urllib.request.Request(f"{url}/v1/console/village", headers=console_headers)
                with local_urlopen(village_request, timeout=1) as response:
                    village = json.loads(response.read().decode("utf-8"))
                self.assertEqual(village["workspace"]["name"], "Test Workspace")
                self.assertEqual(village["agent_limit_per_project"], 12)
                demo_village = next(item for item in village["projects"] if item["project"]["project_id"] == "demo")
                self.assertEqual(demo_village["project"]["agent_count"], 5)
                self.assertTrue(demo_village["agents"])
                self.assertTrue(all(agent["presence"] != "offline" for agent in demo_village["agents"]))
                self.assertLessEqual(len(demo_village["agents"]), village["agent_limit_per_project"])
                self.assertTrue(any(message["message_id"] == msg["message_id"] for message in demo_village["recent_messages"]))

                project_request = urllib.request.Request(f"{url}/v1/console/projects/demo", headers=console_headers)
                with local_urlopen(project_request, timeout=1) as response:
                    project_console = json.loads(response.read().decode("utf-8"))
                self.assertEqual(project_console["project"]["project_id"], "demo")
                self.assertGreaterEqual(len(project_console["agents"]), 5)
                self.assertEqual(project_console["tasks"][0]["task_id"], task["task_id"])
                self.assertTrue(any(message["message_id"] == msg["message_id"] for message in project_console["messages"]))
                self.assertTrue(all(message["recipient_agent_id"] is None for message in project_console["broadcasts"]))
                self.assertTrue(all(message["recipient_agent_id"] is not None for message in project_console["direct_messages"]))
                self.assertTrue(any(message["message_id"] == broadcast["message_id"] for message in project_console["broadcasts"]))
                self.assertTrue(any(message["message_id"] == msg["message_id"] for message in project_console["direct_messages"]))
                self.assertTrue(any(event["event_type"] == "task.updated" for event in project_console["activity"]))
                self.assertTrue(any(event["event_type"] == "agent.status_changed" for event in project_console["activity"]))
                self.assertTrue(any(lease["lease_id"] == lease_b["lease_id"] for lease in project_console["leases"]))

                summary_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/summary",
                    headers=console_headers,
                )
                with local_urlopen(summary_request, timeout=1) as response:
                    project_summary = json.loads(response.read().decode("utf-8"))
                self.assertEqual(project_summary["project"]["project_id"], "demo")
                self.assertLessEqual(len(project_summary["agents"]), 4)
                self.assertLessEqual(len(project_summary["tasks"]), 5)
                self.assertLessEqual(len(project_summary["broadcasts"]), 3)
                self.assertLessEqual(len(project_summary["activity"]), 30)
                self.assertNotIn("direct_messages", project_summary)
                self.assertNotIn("leases", project_summary)

                agents_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/agents?limit=3&filter=all",
                    headers=console_headers,
                )
                with local_urlopen(agents_request, timeout=1) as response:
                    first_agents_page = json.loads(response.read().decode("utf-8"))
                self.assertEqual(len(first_agents_page["agents"]), 3)
                self.assertTrue(first_agents_page["page"]["has_more"])
                agent_cursor = first_agents_page["page"]["next_cursor"]
                next_agent_query = urllib.parse.urlencode({"limit": 3, "filter": "all", "cursor": agent_cursor})
                next_agents_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/agents?{next_agent_query}",
                    headers=console_headers,
                )
                with local_urlopen(next_agents_request, timeout=1) as response:
                    second_agents_page = json.loads(response.read().decode("utf-8"))
                first_agent_ids = {agent["agent_id"] for agent in first_agents_page["agents"]}
                second_agent_ids = {agent["agent_id"] for agent in second_agents_page["agents"]}
                self.assertFalse(first_agent_ids & second_agent_ids)
                self.assertEqual(
                    first_agent_ids | second_agent_ids,
                    {"agent_a", "agent_b", "agent_c", "agent_file", "agent_header"},
                )

                message_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/messages?limit=1",
                    headers=console_headers,
                )
                with local_urlopen(message_request, timeout=1) as response:
                    first_message_page = json.loads(response.read().decode("utf-8"))
                self.assertEqual(len(first_message_page["messages"]), 1)
                self.assertTrue(first_message_page["page"]["has_more"])
                message_cursor = first_message_page["page"]["next_cursor"]
                next_message_query = urllib.parse.urlencode({"limit": 1, "cursor": message_cursor})
                next_message_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/messages?{next_message_query}",
                    headers=console_headers,
                )
                with local_urlopen(next_message_request, timeout=1) as response:
                    second_message_page = json.loads(response.read().decode("utf-8"))
                self.assertNotEqual(
                    first_message_page["messages"][0]["message_id"],
                    second_message_page["messages"][0]["message_id"],
                )

                agent_detail_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/agents/agent_a?limit=10",
                    headers=console_headers,
                )
                with local_urlopen(agent_detail_request, timeout=1) as response:
                    agent_detail = json.loads(response.read().decode("utf-8"))
                self.assertEqual(agent_detail["agent"]["agent_id"], "agent_a")
                self.assertTrue(agent_detail["direct_messages"]["items"])
                self.assertTrue(all(
                    message["recipient_agent_id"] is not None
                    and "agent_a" in {message["sender_agent_id"], message["recipient_agent_id"]}
                    for message in agent_detail["direct_messages"]["items"]
                ))

                invalid_cursor_query = urllib.parse.urlencode({"limit": 2, "cursor": agent_cursor})
                invalid_cursor_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/tasks?{invalid_cursor_query}",
                    headers=console_headers,
                )
                with self.assertRaises(urllib.error.HTTPError) as invalid_cursor_error:
                    local_urlopen(invalid_cursor_request, timeout=1)
                self.assertEqual(invalid_cursor_error.exception.code, 400)

                invalid_resource_request = urllib.request.Request(
                    f"{url}/v1/console/projects/demo/tasks/unexpected",
                    headers=console_headers,
                )
                with self.assertRaises(urllib.error.HTTPError) as invalid_resource_error:
                    local_urlopen(invalid_resource_request, timeout=1)
                self.assertEqual(invalid_resource_error.exception.code, 404)
                self.assertFalse((home / "board").exists())
            finally:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
