from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from commons import relay  # noqa: E402


DB_PATH = Path("/tmp/commons-console-e2e.db")
DEMO_USER_NAME = "Sergio"
DEMO_USER_PREFIX = "sergio-"


def attributed_handle(handle: str) -> str:
    return handle if handle.startswith(DEMO_USER_PREFIX) else f"{DEMO_USER_PREFIX}{handle}"

LIVE_DEMO_AGENTS = (
    ("commons-team", "agent_codex_console", "busy"),
    ("commons-team", "agent_claude_relay", "busy"),
    ("commons-team", "agent_claude_docs", "idle"),
    ("platform-api", "agent_codex_platform", "busy"),
)

MANY_PROJECT_AGENTS = (
    ("identity-edge", "agent_identity_edge", "codex", "identity-edge", "ID7E21", "busy"),
    ("wallet-mobile", "agent_wallet_mobile", "claude-code", "wallet-mobile", "WM8B42", "idle"),
    ("payments-core", "agent_payments_core", "codex", "payments-core", "PC5D72", "busy"),
    ("developer-platform", "agent_developer_platform", "claude-code", "developer-platform", "DP9F31", "idle"),
    ("risk-engine", "agent_risk_engine", "codex", "risk-engine", "RE7P22", "busy"),
    ("growth-automation", "agent_growth_automation", "claude-code", "growth-automation", "GA4K66", "idle"),
    ("release-ops", "agent_release_ops", "codex", "release-ops", "RO6M83", "busy"),
)

LIVE_DEMO_MESSAGES = (
    {
        "project_id": "commons-team",
        "sender_agent_id": "agent_codex_console",
        "recipient": "broadcast",
        "message_type": "status",
        "body": "LIVE: polishing the pixel village and checking the responsive Console.",
    },
    {
        "project_id": "commons-team",
        "sender_agent_id": "agent_claude_relay",
        "recipient": "@sergio-codex-console",
        "message_type": "review",
        "body": "The Relay stream is healthy. I am checking the next activity event now.",
    },
    {
        "project_id": "commons-team",
        "sender_agent_id": "agent_claude_docs",
        "recipient": "broadcast",
        "message_type": "status",
        "body": "Docs are aligned with the current onboarding and private Relay model.",
    },
    {
        "project_id": "platform-api",
        "sender_agent_id": "agent_codex_platform",
        "recipient": "broadcast",
        "message_type": "status",
        "body": "Staging smoke checks are running against the latest API build.",
    },
)


def iso_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def reset_db() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)


def seed() -> None:
    reset_db()
    agents = [
        {
            "project_id": "commons-team",
            "agent_id": "agent_codex_console",
            "runtime": "codex",
            "handle": "codex-console",
            "contact_code": "CX7A21",
            "name": "Console Builder",
            "workspace": "commons",
            "host": "sergio-mac-studio",
        },
        {
            "project_id": "commons-team",
            "agent_id": "agent_claude_relay",
            "runtime": "claude-code",
            "handle": "claude-relay",
            "contact_code": "CL8B42",
            "name": "Relay Engineer",
            "workspace": "commons",
            "host": "sergio-macbook-pro",
        },
        {
            "project_id": "commons-team",
            "agent_id": "agent_codex_review",
            "runtime": "codex",
            "handle": "codex-review",
            "contact_code": "CR5D72",
            "name": "Release Reviewer",
            "workspace": "commons",
            "host": "sergio-mac-studio",
        },
        {
            "project_id": "commons-team",
            "agent_id": "agent_claude_docs",
            "runtime": "claude-code",
            "handle": "claude-docs",
            "contact_code": "CD9F31",
            "name": "Docs Agent",
            "workspace": "commons-docs",
            "host": "docs-runner",
        },
        {
            "project_id": "platform-api",
            "agent_id": "agent_codex_platform",
            "runtime": "codex",
            "handle": "codex-platform",
            "contact_code": "XR7P22",
            "name": "Platform Integrator",
            "workspace": "platform-api",
            "host": "staging-workstation",
        },
    ]
    agents.extend(
        {
            "project_id": "platform-api",
            "agent_id": f"agent_platform_archive_{index:02d}",
            "runtime": "codex",
            "handle": f"platform-archive-{index:02d}",
            "name": f"Archived Platform Agent {index:02d}",
            "workspace": "platform-api",
        }
        for index in range(55)
    )
    if os.environ.get("COMMONS_FIXTURE_MANY_PROJECTS", "").lower() in {"1", "true", "yes"}:
        agents.extend(
            {
                "project_id": project_id,
                "agent_id": agent_id,
                "runtime": runtime,
                "handle": handle,
                "contact_code": contact_code,
                "name": handle.replace("-", " ").title(),
                "workspace": project_id,
            }
            for project_id, agent_id, runtime, handle, contact_code, _status in MANY_PROJECT_AGENTS
        )
    for agent in agents:
        attributed_agent = dict(agent)
        attributed_agent["user_name"] = DEMO_USER_NAME
        attributed_agent["handle"] = attributed_handle(str(agent["handle"]))
        relay.register_agent(attributed_agent, str(DB_PATH))

    architecture = relay.create_remote_task(
        {
            "project_id": "commons-team",
            "title": "Ship Commons Console",
            "summary": "Build and deploy the private Relay operations interface.",
            "owner_agent_id": "agent_codex_console",
            "status": "in_progress",
            "current_step": "Validate the responsive dashboard",
            "next_step": "Deploy the production bundle",
            "progress_percent": 68,
        },
        str(DB_PATH),
    )
    relay.create_remote_task(
        {
            "project_id": "commons-team",
            "title": "Harden operator authentication",
            "summary": "Review session cookie and project isolation behavior.",
            "owner_agent_id": "agent_claude_relay",
            "status": "blocked",
            "current_step": "Wait for deployment policy review",
            "next_step": "Run the cross-project access suite",
            "blocked_reason": "Deployment policy review is pending.",
            "progress_percent": 42,
        },
        str(DB_PATH),
    )
    relay.create_remote_task(
        {
            "project_id": "commons-team",
            "title": "Review production rollout",
            "owner_agent_id": "agent_codex_review",
            "status": "ready_for_review",
            "current_step": "Inspect deployment evidence",
            "next_step": "Publish release verdict",
            "progress_percent": 85,
        },
        str(DB_PATH),
    )
    docs_task = relay.create_remote_task(
        {
            "project_id": "commons-team",
            "title": "Document Console operations",
            "owner_agent_id": "agent_claude_docs",
            "status": "completed",
            "current_step": "Complete",
            "next_step": "None",
            "progress_percent": 100,
        },
        str(DB_PATH),
    )
    relay.create_remote_task(
        {
            "project_id": "platform-api",
            "title": "Validate the staging API",
            "owner_agent_id": "agent_codex_platform",
            "status": "in_progress",
            "current_step": "Run ledger smoke checks",
            "next_step": "Publish signed evidence",
            "progress_percent": 54,
        },
        str(DB_PATH),
    )

    plan = relay.send_message(
        {
            "project_id": "commons-team",
            "sender_agent_id": "agent_codex_console",
            "recipient": "broadcast",
            "message_type": "plan",
            "body": f"PLAN [{architecture['task_id']}]: finish the responsive Console, run browser E2E, then deploy behind Caddy.",
        },
        str(DB_PATH),
    )
    direct = relay.send_message(
        {
            "project_id": "commons-team",
            "sender_agent_id": "agent_claude_relay",
            "recipient": "@sergio-codex-console",
            "message_type": "review",
            "body": "The session-cookie boundary looks sound. Please verify SSE reconnect before rollout.",
        },
        str(DB_PATH),
    )
    relay.ack_message(direct["message_id"], "agent_codex_console", str(DB_PATH), "commons-team")
    relay.send_message(
        {
            "project_id": "commons-team",
            "sender_agent_id": "agent_codex_review",
            "recipient": "broadcast",
            "message_type": "status",
            "body": "Release review is active. No P0 findings so far; mobile evidence is still required.",
        },
        str(DB_PATH),
    )
    relay.send_message(
        {
            "project_id": "commons-team",
            "sender_agent_id": "agent_claude_docs",
            "recipient": "broadcast",
            "message_type": "summary",
            "body": f"DONE [{docs_task['task_id']}]: Console operations guide is ready for deployment review.",
        },
        str(DB_PATH),
    )

    active_lease = relay.acquire_lease(
        {
            "project_id": "commons-team",
            "resource_id": "deploy-slot:commons/production",
            "holder_agent_id": "agent_codex_console",
            "mode": "exclusive",
            "ttl": "45m",
            "reason": "Deploy Commons Console",
        },
        str(DB_PATH),
    )
    review_lease = relay.acquire_lease(
        {
            "project_id": "commons-team",
            "resource_id": "path:commons/web",
            "holder_agent_id": "agent_codex_review",
            "mode": "read",
            "ttl": "30m",
            "reason": "Review frontend changes",
        },
        str(DB_PATH),
    )
    relay.release_lease(
        review_lease["lease_id"],
        "agent_codex_review",
        str(DB_PATH),
        "commons-team",
        review_lease["fencing_epoch"],
    )

    with relay.connect(str(DB_PATH)) as conn, relay.transaction(conn):
        conn.execute(
            "UPDATE agents SET heartbeat_at = ?, status = 'idle' WHERE project_id = 'commons-team' AND agent_id = 'agent_claude_docs'",
            (iso_ago(5),),
        )
        conn.execute(
            "UPDATE agents SET heartbeat_at = ?, status = 'offline' WHERE project_id = 'commons-team' AND agent_id = 'agent_codex_review'",
            (iso_ago(22),),
        )
        conn.execute(
            "UPDATE agents SET heartbeat_at = ?, status = 'offline' WHERE project_id = 'platform-api' AND agent_id LIKE 'agent_platform_archive_%'",
            (iso_ago(24 * 60),),
        )
        relay.audit(
            conn,
            "deploy.ready",
            {"lease_id": active_lease["lease_id"], "task_id": architecture["task_id"], "message_id": plan["message_id"]},
            "commons-team",
            "agent_codex_console",
            "deploy-slot:commons/production",
        )


def run_live_demo() -> None:
    interval = max(4.0, float(os.environ.get("COMMONS_FIXTURE_LIVE_DEMO_INTERVAL", "12")))
    message_index = 0
    demo_agents = list(LIVE_DEMO_AGENTS)
    if os.environ.get("COMMONS_FIXTURE_MANY_PROJECTS", "").lower() in {"1", "true", "yes"}:
        demo_agents.extend(
            (project_id, agent_id, status)
            for project_id, agent_id, _runtime, _handle, _contact_code, status in MANY_PROJECT_AGENTS
        )
    while True:
        try:
            for project_id, agent_id, status in demo_agents:
                relay.heartbeat_agent(
                    {
                        "project_id": project_id,
                        "agent_id": agent_id,
                        "status": status,
                    },
                    str(DB_PATH),
                )
            relay.send_message(LIVE_DEMO_MESSAGES[message_index % len(LIVE_DEMO_MESSAGES)], str(DB_PATH))
            message_index += 1
        except Exception as exc:  # pragma: no cover - local preview diagnostics only
            print(f"Live demo update failed: {exc}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    os.environ["COMMONS_RELAY_TOKEN"] = "relay-e2e-token"
    os.environ["COMMONS_CONSOLE_TOKEN"] = "console-e2e-token"
    os.environ["COMMONS_WORKSPACE_NAME"] = "T54 Agent Workspace"
    seed()
    if os.environ.get("COMMONS_FIXTURE_LIVE_DEMO", "").lower() in {"1", "true", "yes"}:
        threading.Thread(target=run_live_demo, name="commons-live-demo", daemon=True).start()
    relay.serve(host="127.0.0.1", port=8766, db=str(DB_PATH))
