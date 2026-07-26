"""Core Commons service operations."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import board
from .db import connect, init_db, transaction
from .paths import artifact_dir, bin_dir, board_dir, config_path, db_path, ensure_base_dirs, runtime_tests_dir
from .util import (
    current_pid,
    hash_event,
    hostname,
    infer_repo,
    json_dumps,
    make_id,
    now_ts,
    seconds_from_ttl,
    utc_now,
)

LEASE_COMPAT: dict[str, set[str]] = {
    "observe": {"observe", "read", "write"},
    "read": {"observe", "read"},
    "write": {"observe"},
    "exclusive": set(),
    "maintenance": set(),
}
FENCED_LEASE_MODES = {"write", "exclusive", "maintenance"}

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s'\";]+)"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


class CommonsError(Exception):
    pass


class PolicyDenied(CommonsError):
    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


def initialize() -> dict[str, Any]:
    ensure_base_dirs()
    init_db()
    if not config_path().exists():
        config_path().write_text(
            """[daemon]\nhost = "127.0.0.1"\nport = 8765\n\n[policy]\ndefault_lease_ttl = "30m"\nstale_agent_after = "90s"\n""",
            encoding="utf-8",
        )
        config_path().chmod(0o600)
    return {"ok": True, "config": str(config_path())}


def skill_source_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / ".agents" / "skills" / "commons"
    if (source / "SKILL.md").exists():
        return source
    packaged_source = Path(__file__).resolve().parent / "skill_template"
    if (packaged_source / "SKILL.md").exists():
        return packaged_source
    raise CommonsError(f"cannot locate Commons skill source at {source} or {packaged_source}")


def cli_shim_path() -> Path:
    return bin_dir() / "commons"


def install_cli_shim() -> dict[str, Any]:
    ensure_base_dirs()
    shim = cli_shim_path()
    repo_root = Path(__file__).resolve().parents[1]
    # Resolving a venv symlink escapes the environment and can load another
    # globally installed Commons version. Keep the interpreter path verbatim.
    python_executable = Path(sys.executable).absolute()
    script = f"""#!/usr/bin/env bash
set -euo pipefail

COMMONS_PYTHON={shlex.quote(str(python_executable))}
COMMONS_SOURCE={shlex.quote(str(repo_root))}

if [ -f "$COMMONS_SOURCE/commons/cli.py" ]; then
  export PYTHONPATH="$COMMONS_SOURCE${{PYTHONPATH:+:$PYTHONPATH}}"
  exec "$COMMONS_PYTHON" -m commons.cli "$@"
fi

if "$COMMONS_PYTHON" -c 'import commons.cli' >/dev/null 2>&1; then
  exec "$COMMONS_PYTHON" -m commons.cli "$@"
fi

echo "Commons CLI is not importable. Reinstall Commons or run from the Commons repository." >&2
exit 127
"""
    shim.write_text(script, encoding="utf-8")
    shim.chmod(0o755)
    return {
        "path": str(shim),
        "exists": shim.exists(),
        "python": str(python_executable),
        "source": str(repo_root),
    }


def install_skill(target: str = "both", scope: str = "user", project_dir: str | None = None) -> dict[str, Any]:
    if scope not in {"user", "project"}:
        raise CommonsError(f"unknown skill scope: {scope}")
    shim = install_cli_shim()
    source = skill_source_dir()
    project = Path(project_dir or os.getcwd()).resolve()
    installs: list[dict[str, str]] = []
    targets = ["codex", "claude"] if target == "both" else [target]
    for item in targets:
        if item not in {"codex", "claude"}:
            raise CommonsError(f"unknown skill target: {item}")
        if item == "codex":
            base = Path.home() / ".codex" / "skills" if scope == "user" else project / ".agents" / "skills"
        else:
            base = Path.home() / ".claude" / "skills" if scope == "user" else project / ".claude" / "skills"
        dest = base / "commons"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, dirs_exist_ok=True)
        installs.append({"target": item, "scope": scope, "path": str(dest)})
    skill_hash = hashlib.sha256((source / "SKILL.md").read_bytes()).hexdigest()
    return {
        "ok": True,
        "version": __version__,
        "skill_sha256": skill_hash,
        "installed": installs,
        "cli": {"shim_path": shim["path"], "shim_exists": shim["exists"]},
    }


def doctor(fix: bool = False, project_dir: str | None = None) -> dict[str, Any]:
    project = Path(project_dir or os.getcwd()).resolve()
    from . import scope as scope_config

    resolved_scope = scope_config.resolve(str(project))
    local_state_required = resolved_scope["mode"] == "local"
    repaired: list[str] = []
    if fix:
        initialize()
        sync_board()
        shim = install_cli_shim()
        repaired.append("initialized local state and synchronized filesystem board")
        repaired.append(f"installed Commons CLI shim at {shim['path']}")
    elif local_state_required:
        initialize()
        board.ensure_board()

    board_root = board_dir()
    board_subdirs = {name: (board_root / name).is_dir() for name in board.BOARD_SUBDIRS}
    missing_board_dirs = [name for name, exists in board_subdirs.items() if not exists]

    try:
        source_path = skill_source_dir()
        source = str(source_path)
        expected_skill_hash = hashlib.sha256((source_path / "SKILL.md").read_bytes()).hexdigest()
    except CommonsError:
        source = None
        expected_skill_hash = None

    def installed_skill_hash(path: Path) -> str | None:
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            return None
        return hashlib.sha256(skill_file.read_bytes()).hexdigest()

    def skill_paths(target: str) -> dict[str, Any]:
        if target == "codex":
            user_path = Path.home() / ".codex" / "skills" / "commons"
            project_path = project / ".agents" / "skills" / "commons"
        else:
            user_path = Path.home() / ".claude" / "skills" / "commons"
            project_path = project / ".claude" / "skills" / "commons"
        user_hash = installed_skill_hash(user_path)
        project_hash = installed_skill_hash(project_path)
        return {
            "user_path": str(user_path),
            "project_path": str(project_path),
            "user_installed": user_hash is not None,
            "project_installed": project_hash is not None,
            "user_sha256": user_hash,
            "project_sha256": project_hash,
            "expected_sha256": expected_skill_hash,
            "user_up_to_date": bool(user_hash and expected_skill_hash and user_hash == expected_skill_hash),
            "project_up_to_date": bool(project_hash and expected_skill_hash and project_hash == expected_skill_hash),
        }

    runtime_checks = {
        name: {"available": bool(path), "path": path}
        for name, path in {
            "codex": shutil.which("codex"),
            "claude": shutil.which("claude"),
        }.items()
    }
    shim = cli_shim_path()
    cli_path = shutil.which("commons")
    cli_check = {
        "path": cli_path,
        "available_in_path": bool(cli_path),
        "shim_path": str(shim),
        "shim_exists": shim.exists(),
        "recommended": str(shim) if shim.exists() else cli_path,
    }
    status_snapshot = (
        current_status()
        if db_path().exists()
        else {
            "agents": [],
            "tasks": [],
            "active_leases": [],
            "unread_messages": [],
        }
    )
    errors: list[str] = []
    warnings: list[str] = []
    if local_state_required and missing_board_dirs:
        errors.append(f"missing board directories: {', '.join(missing_board_dirs)}")
    for runtime, check in runtime_checks.items():
        if not check["available"]:
            warnings.append(f"{runtime} runtime not found in PATH; runtime smoke tests will be skipped")
    if not cli_check["available_in_path"] and not cli_check["shim_exists"]:
        warnings.append(f"commons CLI not found in PATH and shim missing; run doctor --fix or install-skill")

    skills = {
        "source": source,
        "source_sha256": expected_skill_hash,
        "codex": skill_paths("codex"),
        "claude": skill_paths("claude"),
    }
    for runtime in ("codex", "claude"):
        check = skills[runtime]
        for install_scope in ("user", "project"):
            if check[f"{install_scope}_installed"] and not check[f"{install_scope}_up_to_date"]:
                warnings.append(
                    f"{runtime} {install_scope} Commons skill is outdated; "
                    f"run commons install-skill --target {runtime} --scope {install_scope}"
                )

    return {
        "ok": not errors,
        "mode": "filesystem-first",
        "mcp_required": False,
        "scope": resolved_scope,
        "config": str(config_path()),
        "db": {"path": str(db_path()), "exists": db_path().exists()},
        "board": {
            "path": str(board_root),
            "exists": board_root.exists(),
            "required": local_state_required,
            "subdirs": board_subdirs,
            "status_file_exists": (board_root / "status.json").exists(),
        },
        "daemon": {"required": False},
        "cli": cli_check,
        "skills": skills,
        "runtimes": runtime_checks,
        "counts": {
            "agents": len(status_snapshot["agents"]),
            "tasks": len(status_snapshot["tasks"]),
            "active_leases": len(status_snapshot["active_leases"]),
            "unread_messages": len(status_snapshot["unread_messages"]),
        },
        "errors": errors,
        "warnings": warnings,
        "repaired": repaired,
    }


def _runtime_prompt(
    role: str,
    run_id: str,
    runtime: str,
    agent_name: str,
    peer_name: str,
    project: Path,
    resource_id: str,
) -> str:
    if role == "a":
        body = f"""You are Agent A in Commons runtime smoke run {run_id}.

Use the Commons skill. Do not assume MCP is available.

Goal: prove that another local agent can discover your plan, see your resource lease, and coordinate through Commons without the human relaying messages.

Run these steps from this workspace:

```bash
commons doctor --project-dir "{project}" --json
commons agent register --runtime {runtime} --workspace "{project}" --name "{agent_name}" --task "Runtime smoke {run_id}"
```

Save your `agent_id` and `task_id`, then:

```bash
commons plan publish --task <task_id> --agent <agent_id> --summary "Runtime smoke {run_id}: Agent A will hold {resource_id} briefly and wait for Agent B."
commons lease acquire {resource_id} --mode write --ttl 10m --agent <agent_id> --reason "Runtime smoke {run_id}: Agent A fixture hold"
commons msg send @broadcast "Runtime smoke {run_id}: Agent A holds {resource_id}; Agent B should request coordination through Commons." --sender <agent_id> --task <task_id>
commons inbox --agent <agent_id>
```

If Agent B asks for handoff, reply with the lease id and release the lease when done:

```bash
commons msg reply <message_id> "Runtime smoke {run_id}: I will release {resource_id} after your denial is visible." --sender <agent_id>
commons lease release <lease_id> --agent <agent_id> --fencing-epoch <fencing_epoch>
```
"""
    else:
        body = f"""You are Agent B in Commons runtime smoke run {run_id}.

Use the Commons skill. Do not assume MCP is available.

Goal: discover Agent A through Commons, observe the planned shared resource, hit a safe lease denial, and coordinate by message instead of asking the human to relay context.

Run these steps from this workspace:

```bash
commons doctor --project-dir "{project}" --json
commons agent register --runtime {runtime} --workspace "{project}" --name "{agent_name}" --task "Runtime smoke {run_id} Agent B"
commons agent list
commons inbox
```

Find the agent named `{peer_name}`, save your `agent_id` and `task_id`, then:

```bash
commons plan publish --task <task_id> --agent <agent_id> --summary "Runtime smoke {run_id}: Agent B will coordinate for {resource_id}."
commons lease acquire {resource_id} --mode exclusive --ttl 5m --agent <agent_id> --reason "Runtime smoke {run_id}: intentional conflict"
```

The lease acquire should be denied. Do not bypass it. Send Agent A a message:

```bash
commons msg send @<agent_a_id> "Runtime smoke {run_id}: I saw your {resource_id} lease denial. Please release it when ready." --sender <agent_id> --task <task_id>
commons context publish --task <task_id> --agent <agent_id> --summary "Runtime smoke {run_id}: Agent B observed Commons denial and did not run the conflicting action."
```
"""
    return body.strip() + "\n"


def prepare_runtime_smoke(
    agents: str = "codex,claude-code",
    scenario: str = "skill-handshake",
    project_dir: str | None = None,
) -> dict[str, Any]:
    if scenario != "skill-handshake":
        raise CommonsError(f"unknown runtime smoke scenario: {scenario}")
    initialize()
    runtimes = [item.strip() for item in agents.split(",") if item.strip()]
    while len(runtimes) < 2:
        runtimes.append("custom")
    run_id = make_id("runtime")
    suffix = run_id.split("_", 1)[1][:8]
    resource_id = f"env:fixture/runtime-{suffix}"
    project = Path(project_dir or os.getcwd()).resolve()
    agent_a_name = f"runtime-a-{suffix}"
    agent_b_name = f"runtime-b-{suffix}"
    root = runtime_tests_dir() / run_id
    root.mkdir(parents=True, exist_ok=True)
    prompts = {
        "agent_a": _runtime_prompt("a", run_id, runtimes[0], agent_a_name, agent_b_name, project, resource_id),
        "agent_b": _runtime_prompt("b", run_id, runtimes[1], agent_b_name, agent_a_name, project, resource_id),
    }
    prompt_paths: dict[str, str] = {}
    for name, content in prompts.items():
        path = root / f"{name}_prompt.md"
        path.write_text(content, encoding="utf-8")
        prompt_paths[name] = str(path)
    manifest = {
        "run_id": run_id,
        "scenario": scenario,
        "project_dir": str(project),
        "resource_id": resource_id,
        "agents": [
            {"role": "agent_a", "runtime": runtimes[0], "name": agent_a_name},
            {"role": "agent_b", "runtime": runtimes[1], "name": agent_b_name},
        ],
        "prompt_paths": prompt_paths,
        "created_at": utc_now(),
    }
    board.write_json_atomic(root / "manifest.json", manifest)
    return {"ok": True, "run_id": run_id, "dir": str(root), **manifest}


def verify_runtime_smoke(run_id: str) -> dict[str, Any]:
    initialize()
    root = runtime_tests_dir() / run_id
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise CommonsError(f"unknown runtime smoke run: {run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    resource_id = manifest["resource_id"]
    agent_names = [item["name"] for item in manifest["agents"]]
    like_run = f"%{run_id}%"
    like_resource = f"%{resource_id}%"
    with connect() as conn:
        agents = [
            _row_to_dict(r)
            for r in conn.execute(
                f"SELECT * FROM agents WHERE name IN ({','.join('?' for _ in agent_names)}) ORDER BY registered_at",
                agent_names,
            )
        ]
        plans = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM plans WHERE summary LIKE ? OR body LIKE ? ORDER BY created_at",
                (like_run, like_run),
            )
        ]
        messages = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM messages WHERE body LIKE ? OR body LIKE ? ORDER BY created_at",
                (like_run, like_resource),
            )
        ]
        leases = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM leases WHERE canonical_resource_id = ? ORDER BY acquired_at",
                (canonical_resource_id(resource_id),),
            )
        ]
        denials = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM audit_events WHERE event_type = 'lease.denied' AND payload LIKE ? ORDER BY event_id",
                (like_resource,),
            )
        ]
    checks = {
        "agent_a_registered": any(item["name"] == agent_names[0] for item in agents),
        "agent_b_registered": any(item["name"] == agent_names[1] for item in agents),
        "plan_published": bool(plans),
        "message_exchange": len(messages) >= 2,
        "lease_recorded": bool(leases),
        "lease_denial_recorded": bool(denials),
        "board_status_exists": (board.board_path() and (board.ensure_board() / "status.json").exists()),
    }
    return {
        "ok": all(checks.values()),
        "run_id": run_id,
        "scenario": manifest["scenario"],
        "resource_id": resource_id,
        "checks": checks,
        "counts": {
            "agents": len(agents),
            "plans": len(plans),
            "messages": len(messages),
            "leases": len(leases),
            "denials": len(denials),
        },
        "manifest": str(manifest_path),
    }


def _audit(
    conn,
    event_type: str,
    payload: dict[str, Any],
    actor_agent_id: str | None = None,
    task_id: str | None = None,
    resource_id: str | None = None,
) -> int:
    row = conn.execute(
        "SELECT event_hash FROM audit_events ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    prev_hash = row["event_hash"] if row else "0" * 64
    created_at = utc_now()
    event_hash = hash_event(prev_hash, event_type, payload, created_at)
    cur = conn.execute(
        """
        INSERT INTO audit_events(event_type, actor_agent_id, task_id, resource_id, payload, prev_hash, event_hash, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            actor_agent_id,
            task_id,
            resource_id,
            json_dumps(payload),
            prev_hash,
            event_hash,
            created_at,
        ),
    )
    event_id = int(cur.lastrowid)
    conn.execute("INSERT INTO event_outbox(event_id) VALUES(?)", (event_id,))
    board.publish_audit_event(
        {
            "event_id": event_id,
            "event_type": event_type,
            "actor_agent_id": actor_agent_id,
            "task_id": task_id,
            "resource_id": resource_id,
            "payload": payload,
            "created_at": created_at,
            "event_hash": event_hash,
        }
    )
    return event_id


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def redact_text(value: str) -> tuple[str, bool]:
    redacted = value
    changed = False
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)"):
            redacted, count = pattern.subn(lambda m: f"{m.group(1)}=[REDACTED]", redacted)
        else:
            redacted, count = pattern.subn("[REDACTED]", redacted)
        changed = changed or bool(count)
    return redacted, changed


def _message_dict(row) -> dict[str, Any]:
    payload = _row_to_dict(row)
    payload["untrusted"] = True
    return payload


def register_agent(
    runtime: str = "custom",
    workspace: str | None = None,
    name: str | None = None,
    task: str | None = None,
    runtime_version: str | None = None,
) -> dict[str, Any]:
    init_db()
    workspace_path = Path(workspace or os.getcwd()).resolve()
    repo = infer_repo(workspace_path)
    agent_id = make_id("agent")
    timestamp = utc_now()
    with connect() as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO agents(agent_id, name, runtime, runtime_version, host, pid, workspace, repo, branch, capabilities, status, registered_at, heartbeat_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'online', ?, ?)
            """,
            (
                agent_id,
                name,
                runtime,
                runtime_version,
                hostname(),
                current_pid(),
                str(workspace_path),
                repo,
                None,
                "[]",
                timestamp,
                timestamp,
            ),
        )
        task_id = None
        if task:
            task_id = make_id("task")
            conn.execute(
                """
                INSERT INTO tasks(task_id, title, status, owner_agent_id, created_at, updated_at)
                VALUES(?, ?, 'claimed', ?, ?, ?)
                """,
                (task_id, task, agent_id, timestamp, timestamp),
            )
            conn.execute("UPDATE agents SET task_id = ? WHERE agent_id = ?", (task_id, agent_id))
        _audit(
            conn,
            "agent.registered",
            {"agent_id": agent_id, "runtime": runtime, "workspace": str(workspace_path)},
            actor_agent_id=agent_id,
            task_id=task_id,
        )
        agent = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        task_row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone() if task_id else None
    agent_payload = _row_to_dict(agent)
    board.publish_agent(agent_payload)
    if task_row:
        board.publish_task(_row_to_dict(task_row))
    board.publish_status(current_status())
    return {"agent_id": agent_id, "task_id": task_id, "runtime": runtime, "workspace": str(workspace_path)}


def heartbeat(agent_id: str, status: str | None = None) -> dict[str, Any]:
    init_db()
    timestamp = utc_now()
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown agent: {agent_id}")
        conn.execute(
            "UPDATE agents SET heartbeat_at = ?, status = COALESCE(?, status) WHERE agent_id = ?",
            (timestamp, status, agent_id),
        )
        _audit(conn, "agent.heartbeat", {"agent_id": agent_id, "status": status}, actor_agent_id=agent_id)
        agent = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    board.publish_agent(_row_to_dict(agent))
    board.publish_status(current_status())
    return {"ok": True, "agent_id": agent_id, "heartbeat_at": timestamp}


def unregister_agent(agent_id: str) -> dict[str, Any]:
    init_db()
    timestamp = utc_now()
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown agent: {agent_id}")
        conn.execute(
            "UPDATE agents SET status = 'offline', heartbeat_at = ? WHERE agent_id = ?",
            (timestamp, agent_id),
        )
        _audit(conn, "agent.unregistered", {"agent_id": agent_id}, actor_agent_id=agent_id)
        agent = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    board.publish_agent(_row_to_dict(agent))
    board.publish_status(current_status())
    return {"ok": True, "agent_id": agent_id, "status": "offline"}


def list_agents() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY registered_at")]


def create_task(title: str, owner_agent_id: str | None = None) -> dict[str, Any]:
    init_db()
    task_id = make_id("task")
    ts = utc_now()
    with connect() as conn, transaction(conn):
        conn.execute(
            "INSERT INTO tasks(task_id, title, status, owner_agent_id, created_at, updated_at) VALUES(?, ?, 'created', ?, ?, ?)",
            (task_id, title, owner_agent_id, ts, ts),
        )
        _audit(conn, "task.created", {"task_id": task_id, "title": title}, actor_agent_id=owner_agent_id, task_id=task_id)
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    board.publish_task(_row_to_dict(task))
    board.publish_status(current_status())
    return {"task_id": task_id, "title": title, "status": "created"}


def update_task(task_id: str, status: str | None = None, summary: str | None = None, owner_agent_id: str | None = None) -> dict[str, Any]:
    init_db()
    ts = utc_now()
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown task: {task_id}")
        conn.execute(
            """
            UPDATE tasks
            SET status = COALESCE(?, status), summary = COALESCE(?, summary),
                owner_agent_id = COALESCE(?, owner_agent_id), updated_at = ?
            WHERE task_id = ?
            """,
            (status, summary, owner_agent_id, ts, task_id),
        )
        _audit(conn, "task.updated", {"task_id": task_id, "status": status, "summary": summary}, actor_agent_id=owner_agent_id, task_id=task_id)
        updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    board.publish_task(_row_to_dict(updated))
    board.publish_status(current_status())
    return _row_to_dict(updated)


def list_tasks() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC")]


def get_task(task_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown task: {task_id}")
        return _row_to_dict(row)


def publish_plan(task_id: str, summary: str | None = None, body: str | None = None, created_by: str | None = None) -> dict[str, Any]:
    init_db()
    plan_id = make_id("plan")
    ts = utc_now()
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM plans WHERE task_id = ?", (task_id,)).fetchone()
        version = int(row["v"]) + 1
        conn.execute(
            "INSERT INTO plans(plan_id, task_id, version, summary, body, created_by, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
            (plan_id, task_id, version, summary, body, created_by, ts),
        )
        _audit(conn, "plan.published", {"plan_id": plan_id, "task_id": task_id, "version": version, "summary": summary}, actor_agent_id=created_by, task_id=task_id)
        plan = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
    board.publish_plan(_row_to_dict(plan))
    board.publish_status(current_status())
    return {"plan_id": plan_id, "task_id": task_id, "version": version}


def show_plan(task_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM plans WHERE task_id = ? ORDER BY version", (task_id,))]


def diff_plan(task_id: str, from_version: int, to_version: int) -> dict[str, Any]:
    plans = {int(item["version"]): item for item in show_plan(task_id)}
    if from_version not in plans:
        raise CommonsError(f"unknown plan version for {task_id}: {from_version}")
    if to_version not in plans:
        raise CommonsError(f"unknown plan version for {task_id}: {to_version}")

    def text(plan: dict[str, Any]) -> list[str]:
        summary = plan.get("summary") or ""
        body = plan.get("body") or ""
        return [f"summary: {summary}\n", *body.splitlines(keepends=True)]

    diff = "".join(
        difflib.unified_diff(
            text(plans[from_version]),
            text(plans[to_version]),
            fromfile=f"{task_id}@v{from_version}",
            tofile=f"{task_id}@v{to_version}",
        )
    )
    return {"task_id": task_id, "from": from_version, "to": to_version, "diff": diff}


def send_message(
    body: str,
    sender_agent_id: str | None = None,
    recipient_agent_id: str | None = None,
    task_id: str | None = None,
    thread_id: str | None = None,
    message_type: str = "note",
) -> dict[str, Any]:
    init_db()
    ts = utc_now()
    message_id = make_id("msg")
    body, redacted = redact_text(body)
    with connect() as conn, transaction(conn):
        if not thread_id:
            thread_id = make_id("thread")
            conn.execute(
                "INSERT INTO message_threads(thread_id, task_id, subject, created_at) VALUES(?, ?, ?, ?)",
                (thread_id, task_id, body[:80], ts),
            )
        conn.execute(
            """
            INSERT INTO messages(message_id, thread_id, task_id, sender_agent_id, recipient_agent_id, message_type, body, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, thread_id, task_id, sender_agent_id, recipient_agent_id, message_type, body, ts),
        )
        _audit(
            conn,
            "message.sent",
            {"message_id": message_id, "thread_id": thread_id, "recipient": recipient_agent_id, "redacted": redacted},
            actor_agent_id=sender_agent_id,
            task_id=task_id,
        )
        message = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
    board.publish_message(_message_dict(message))
    board.publish_status(current_status())
    return {"message_id": message_id, "thread_id": thread_id, "redacted": redacted}


def inbox(agent_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if agent_id:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE recipient_agent_id = ? OR recipient_agent_id IS NULL
                ORDER BY created_at DESC
                """,
                (agent_id,),
            )
        else:
            rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC")
        return [_message_dict(r) for r in rows]


def read_message(message_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown message: {message_id}")
        return _message_dict(row)


def reply_message(message_id: str, body: str, sender_agent_id: str | None = None) -> dict[str, Any]:
    original = read_message(message_id)
    recipient = original.get("sender_agent_id")
    return send_message(
        body,
        sender_agent_id=sender_agent_id,
        recipient_agent_id=recipient,
        task_id=original.get("task_id"),
        thread_id=original.get("thread_id"),
        message_type="answer",
    )


def publish_context(task_id: str, summary: str, sender_agent_id: str | None = None) -> dict[str, Any]:
    return send_message(
        summary,
        sender_agent_id=sender_agent_id,
        recipient_agent_id=None,
        task_id=task_id,
        message_type="context",
    )


def request_context(recipient_agent_id: str, task_id: str | None, reason: str, sender_agent_id: str | None = None) -> dict[str, Any]:
    return send_message(
        f"Context request: {reason}",
        sender_agent_id=sender_agent_id,
        recipient_agent_id=recipient_agent_id,
        task_id=task_id,
        message_type="context-request",
    )


def ack_message(message_id: str) -> dict[str, Any]:
    init_db()
    ts = utc_now()
    with connect() as conn, transaction(conn):
        conn.execute("UPDATE messages SET acked_at = ? WHERE message_id = ?", (ts, message_id))
        _audit(conn, "message.acked", {"message_id": message_id})
        message = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
    if message:
        board.publish_message(_message_dict(message))
    board.publish_status(current_status())
    return {"ok": True, "message_id": message_id}


def canonical_resource_id(resource_id: str) -> str:
    return resource_id.strip().lower()


def resolve_resource_id(conn, resource_id: str) -> str:
    normalized = canonical_resource_id(resource_id)
    row = conn.execute("SELECT canonical_id FROM resource_aliases WHERE alias = ?", (normalized,)).fetchone()
    if row:
        return row["canonical_id"]
    return normalized


def ensure_resource(conn, resource_id: str, description: str | None = None) -> dict[str, Any]:
    canonical = resolve_resource_id(conn, resource_id)
    row = conn.execute("SELECT * FROM resources WHERE canonical_id = ?", (canonical,)).fetchone()
    if row:
        return _row_to_dict(row)
    ts = utc_now()
    conn.execute(
        "INSERT INTO resources(resource_id, canonical_id, description, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        (resource_id, canonical, description, ts, ts),
    )
    row = conn.execute("SELECT * FROM resources WHERE canonical_id = ?", (canonical,)).fetchone()
    return _row_to_dict(row)


def add_resource_alias(alias: str, canonical_resource: str) -> dict[str, Any]:
    init_db()
    with connect() as conn, transaction(conn):
        resource = ensure_resource(conn, canonical_resource)
        normalized_alias = canonical_resource_id(alias)
        conn.execute(
            "INSERT OR REPLACE INTO resource_aliases(alias, canonical_id) VALUES(?, ?)",
            (normalized_alias, resource["canonical_id"]),
        )
        _audit(
            conn,
            "resource.alias_added",
            {"alias": normalized_alias, "canonical_id": resource["canonical_id"]},
            resource_id=resource["resource_id"],
        )
    board.publish_status(current_status())
    return {"alias": normalized_alias, "canonical_id": resource["canonical_id"]}


def list_resources() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM resources ORDER BY canonical_id")
        return [_row_to_dict(r) for r in rows]


def show_resource(resource_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn, transaction(conn):
        resource = ensure_resource(conn, resource_id)
        leases = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM leases WHERE canonical_resource_id = ? ORDER BY acquired_at DESC",
                (resource["canonical_id"],),
            )
        ]
        aliases = [
            _row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM resource_aliases WHERE canonical_id = ? ORDER BY alias",
                (resource["canonical_id"],),
            )
        ]
    return {**resource, "leases": leases, "aliases": aliases}


def _expire_leases(conn, canonical: str) -> None:
    now = now_ts()
    rows = list(
        conn.execute(
            "SELECT * FROM leases WHERE canonical_resource_id = ? AND state = 'active' AND expires_at <= ?",
            (canonical, now),
        )
    )
    for row in rows:
        conn.execute("UPDATE leases SET state = 'expired' WHERE lease_id = ?", (row["lease_id"],))
        _audit(
            conn,
            "lease.expired",
            {"lease_id": row["lease_id"], "resource_id": row["resource_id"]},
            actor_agent_id=row["holder_agent_id"],
            resource_id=row["resource_id"],
        )


def _lease_conflicts(existing_mode: str, requested_mode: str) -> bool:
    return existing_mode not in LEASE_COMPAT.get(requested_mode, set())


def acquire_lease(
    resource_id: str,
    mode: str = "write",
    ttl: str | None = None,
    reason: str | None = None,
    holder_agent_id: str | None = None,
    wait: bool = False,
) -> dict[str, Any]:
    if mode not in LEASE_COMPAT:
        raise CommonsError(f"invalid lease mode: {mode}")
    init_db()
    ttl_seconds = seconds_from_ttl(ttl)
    denied_details: dict[str, Any] | None = None
    denied_message: str | None = None
    lease_id: str | None = None
    new_epoch: int | None = None
    lease_row = None
    with connect() as conn, transaction(conn):
        resource = ensure_resource(conn, resource_id)
        canonical = resource["canonical_id"]
        _expire_leases(conn, canonical)
        active = list(
            conn.execute(
                "SELECT * FROM leases WHERE canonical_resource_id = ? AND state = 'active' ORDER BY acquired_at",
                (canonical,),
            )
        )
        conflicts = [r for r in active if _lease_conflicts(r["mode"], mode)]
        if conflicts:
            conflict = _row_to_dict(conflicts[0])
            send_action = [
                "commons",
                "msg",
                "send",
                conflict["holder_agent_id"],
                f"Can you release {resource_id} when done?",
            ]
            if holder_agent_id:
                send_action.extend(["--sender", holder_agent_id])
            details = {
                "resource_id": resource_id,
                "mode": mode,
                "holder_agent_id": conflict["holder_agent_id"],
                "holder_lease_id": conflict["lease_id"],
                "holder_mode": conflict["mode"],
                "expires_at": conflict["expires_at"],
                "safe_next_actions": [
                    shlex.join(send_action),
                    shlex.join(["commons", "lease", "conflicts", resource_id, "--mode", mode]),
                ],
            }
            _audit(conn, "lease.denied", details, actor_agent_id=holder_agent_id, resource_id=resource_id)
            denied_details = details
            denied_message = f"lease conflict for {resource_id}"
        else:
            new_epoch = int(resource["fencing_epoch"])
            if mode in FENCED_LEASE_MODES:
                new_epoch += 1
                conn.execute(
                    "UPDATE resources SET fencing_epoch = ?, updated_at = ? WHERE canonical_id = ?",
                    (new_epoch, utc_now(), canonical),
                )
            lease_id = make_id("lease")
            acquired_at = utc_now()
            expires_at = now_ts() + ttl_seconds
            conn.execute(
                """
                INSERT INTO leases(lease_id, resource_id, canonical_resource_id, mode, holder_agent_id, reason, state, fencing_epoch, acquired_at, expires_at)
                VALUES(?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (lease_id, resource_id, canonical, mode, holder_agent_id, reason, new_epoch, acquired_at, expires_at),
            )
            _audit(
                conn,
                "lease.granted",
                {
                    "lease_id": lease_id,
                    "resource_id": resource_id,
                    "mode": mode,
                    "fencing_epoch": new_epoch,
                    "reason": reason,
                },
                actor_agent_id=holder_agent_id,
                resource_id=resource_id,
            )
            lease_row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    if denied_details is not None:
        board.publish_status(current_status())
        raise PolicyDenied(denied_message or f"lease conflict for {resource_id}", denied_details)
    if lease_id is None or new_epoch is None or lease_row is None:
        raise CommonsError("lease acquire failed without denial details")
    lease_payload = _row_to_dict(lease_row)
    board.publish_lease(lease_payload)
    board.publish_status(current_status())
    return {
        "lease_id": lease_id,
        "resource_id": resource_id,
        "mode": mode,
        "holder_agent_id": holder_agent_id,
        "fencing_epoch": new_epoch,
        "expires_at": expires_at,
    }


def release_lease(lease_id: str, holder_agent_id: str | None = None, fencing_epoch: int | None = None) -> dict[str, Any]:
    init_db()
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown lease: {lease_id}")
        if holder_agent_id and row["holder_agent_id"] and holder_agent_id != row["holder_agent_id"]:
            raise PolicyDenied("lease holder mismatch", {"lease_id": lease_id})
        if fencing_epoch is not None and int(row["fencing_epoch"]) != int(fencing_epoch):
            raise PolicyDenied("stale fencing epoch", {"lease_id": lease_id})
        conn.execute(
            "UPDATE leases SET state = 'released', released_at = ? WHERE lease_id = ? AND state = 'active'",
            (utc_now(), lease_id),
        )
        _audit(
            conn,
            "lease.released",
            {"lease_id": lease_id, "resource_id": row["resource_id"]},
            actor_agent_id=holder_agent_id,
            resource_id=row["resource_id"],
        )
        updated = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    board.publish_lease(_row_to_dict(updated))
    board.publish_status(current_status())
    return {"ok": True, "lease_id": lease_id}


def list_leases(active_only: bool = False) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if active_only:
            rows = conn.execute("SELECT * FROM leases WHERE state = 'active' ORDER BY acquired_at DESC")
        else:
            rows = conn.execute("SELECT * FROM leases ORDER BY acquired_at DESC")
        return [_row_to_dict(r) for r in rows]


def lease_conflicts(resource_id: str, mode: str = "write") -> dict[str, Any]:
    init_db()
    with connect() as conn, transaction(conn):
        resource = ensure_resource(conn, resource_id)
        canonical = resource["canonical_id"]
        _expire_leases(conn, canonical)
        active = list(
            conn.execute(
                "SELECT * FROM leases WHERE canonical_resource_id = ? AND state = 'active'",
                (canonical,),
            )
        )
    conflicts = [_row_to_dict(r) for r in active if _lease_conflicts(r["mode"], mode)]
    return {"resource_id": resource_id, "mode": mode, "conflicts": conflicts}


def renew_lease(lease_id: str, ttl: str | None = None, holder_agent_id: str | None = None, fencing_epoch: int | None = None) -> dict[str, Any]:
    init_db()
    ttl_seconds = seconds_from_ttl(ttl)
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown lease: {lease_id}")
        if row["state"] != "active":
            raise PolicyDenied("cannot renew inactive lease", {"lease_id": lease_id, "state": row["state"]})
        if holder_agent_id and row["holder_agent_id"] and holder_agent_id != row["holder_agent_id"]:
            raise PolicyDenied("lease holder mismatch", {"lease_id": lease_id})
        if fencing_epoch is not None and int(row["fencing_epoch"]) != int(fencing_epoch):
            raise PolicyDenied("stale fencing epoch", {"lease_id": lease_id})
        expires_at = now_ts() + ttl_seconds
        conn.execute("UPDATE leases SET expires_at = ? WHERE lease_id = ?", (expires_at, lease_id))
        _audit(
            conn,
            "lease.renewed",
            {"lease_id": lease_id, "expires_at": expires_at},
            actor_agent_id=holder_agent_id,
            resource_id=row["resource_id"],
        )
        updated = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    board.publish_lease(_row_to_dict(updated))
    board.publish_status(current_status())
    return {"ok": True, "lease_id": lease_id, "expires_at": expires_at}


def force_release_lease(lease_id: str, reason: str, actor_agent_id: str | None = None) -> dict[str, Any]:
    init_db()
    if not reason:
        raise CommonsError("force release requires a reason")
    with connect() as conn, transaction(conn):
        row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown lease: {lease_id}")
        conn.execute(
            "UPDATE leases SET state = 'force_released', released_at = ? WHERE lease_id = ? AND state = 'active'",
            (utc_now(), lease_id),
        )
        _audit(
            conn,
            "lease.force_released",
            {"lease_id": lease_id, "reason": reason},
            actor_agent_id=actor_agent_id,
            resource_id=row["resource_id"],
        )
        updated = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
    board.publish_lease(_row_to_dict(updated))
    board.publish_status(current_status())
    return {"ok": True, "lease_id": lease_id, "reason": reason}


def attach_artifact(task_id: str | None, artifact_type: str, path: str, visibility: str = "workspace") -> dict[str, Any]:
    init_db()
    src_input = Path(path).expanduser()
    if any(part == ".." for part in src_input.parts):
        raise CommonsError(f"artifact path traversal is not allowed: {path}")
    if src_input.is_symlink():
        raise CommonsError(f"artifact path must not be a symlink: {path}")
    src = src_input.resolve()
    if not src.exists() or not src.is_file():
        raise CommonsError(f"artifact path is not a file: {path}")
    if artifact_type == "secret-risk":
        visibility = "human-only"
    artifact_id = make_id("artifact")
    dest_dir = artifact_dir() / (task_id or "unscoped")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{artifact_id}-{src.name}"
    redacted = False
    data = src.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        shutil.copy2(src, dest)
    else:
        safe_text, redacted = redact_text(text)
        dest.write_text(safe_text, encoding="utf-8")
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    ts = utc_now()
    with connect() as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO artifacts(artifact_id, task_id, artifact_type, visibility, source_path, stored_path, sha256, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, task_id, artifact_type, visibility, str(src), str(dest), digest, ts),
        )
        _audit(
            conn,
            "artifact.attached",
            {"artifact_id": artifact_id, "type": artifact_type, "redacted": redacted, "visibility": visibility},
            task_id=task_id,
        )
    board.publish_status(current_status())
    return {"artifact_id": artifact_id, "stored_path": str(dest), "sha256": digest, "redacted": redacted, "visibility": visibility}


def list_artifacts(task_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if task_id:
            rows = conn.execute("SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at DESC", (task_id,))
        else:
            rows = conn.execute("SELECT * FROM artifacts ORDER BY created_at DESC")
        return [_row_to_dict(r) for r in rows]


def show_artifact(artifact_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        if not row:
            raise CommonsError(f"unknown artifact: {artifact_id}")
        return _row_to_dict(row)


def audit_recent(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY event_id DESC LIMIT ?", (limit,))
        return [_row_to_dict(r) for r in rows]


def audit_task(task_id: str, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE task_id = ? ORDER BY event_id DESC LIMIT ?",
            (task_id, limit),
        )
        return [_row_to_dict(r) for r in rows]


def audit_resource(resource_id: str, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    canonical = canonical_resource_id(resource_id)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM audit_events
            WHERE lower(resource_id) = ? OR payload LIKE ?
            ORDER BY event_id DESC
            LIMIT ?
            """,
            (canonical, f"%{resource_id}%", limit),
        )
        return [_row_to_dict(r) for r in rows]


def audit_verify() -> dict[str, Any]:
    init_db()
    checked = 0
    errors: list[dict[str, Any]] = []
    expected_prev = "0" * 64
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY event_id")
        for row in rows:
            checked += 1
            payload = json.loads(row["payload"])
            expected_hash = hash_event(expected_prev, row["event_type"], payload, row["created_at"])
            if row["prev_hash"] != expected_prev:
                errors.append({"event_id": row["event_id"], "error": "prev_hash mismatch"})
            if row["event_hash"] != expected_hash:
                errors.append({"event_id": row["event_id"], "error": "event_hash mismatch"})
            expected_prev = row["event_hash"]
    return {"ok": not errors, "checked": checked, "errors": errors}


def export_task_markdown(task_id: str) -> str:
    task = get_task(task_id)
    plans = show_plan(task_id)
    messages = [m for m in inbox(None) if m.get("task_id") == task_id]
    artifacts = list_artifacts(task_id)
    events = audit_task(task_id, limit=200)
    lines = [
        f"# Commons Task Report: {task_id}",
        "",
        f"- Title: {task['title']}",
        f"- Status: {task['status']}",
        f"- Owner: {task.get('owner_agent_id') or ''}",
        f"- Created: {task['created_at']}",
        f"- Updated: {task['updated_at']}",
        "",
        "## Plans",
    ]
    if plans:
        for plan in plans:
            lines.extend(["", f"### Version {plan['version']}", "", plan.get("summary") or ""])
            if plan.get("body"):
                lines.extend(["", plan["body"]])
    else:
        lines.append("")
        lines.append("No plans.")
    lines.extend(["", "## Messages"])
    if messages:
        for msg in messages:
            sender = msg.get("sender_agent_id") or "unknown"
            recipient = msg.get("recipient_agent_id") or "broadcast"
            lines.extend(["", f"- `{msg['message_id']}` {sender} -> {recipient}: {msg['body']}"])
    else:
        lines.append("")
        lines.append("No messages.")
    lines.extend(["", "## Artifacts"])
    if artifacts:
        for artifact in artifacts:
            lines.extend(["", f"- `{artifact['artifact_id']}` {artifact['artifact_type']} {artifact.get('stored_path') or ''}"])
    else:
        lines.append("")
        lines.append("No artifacts.")
    lines.extend(["", "## Audit"])
    for event in reversed(events):
        lines.append(f"- {event['event_id']} {event['event_type']} {event['created_at']}")
    return "\n".join(lines).rstrip() + "\n"


def export_resource_markdown(resource_id: str) -> str:
    leases = [item for item in list_leases(False) if canonical_resource_id(item["resource_id"]) == canonical_resource_id(resource_id)]
    events = audit_resource(resource_id, limit=200)
    lines = [
        f"# Commons Resource Report: {resource_id}",
        "",
        "## Leases",
    ]
    if leases:
        for lease in leases:
            lines.append(
                f"- `{lease['lease_id']}` {lease['mode']} {lease['state']} holder={lease.get('holder_agent_id') or ''} "
                f"epoch={lease['fencing_epoch']}"
            )
    else:
        lines.append("No leases.")
    lines.extend(["", "## Audit"])
    for event in reversed(events):
        lines.append(f"- {event['event_id']} {event['event_type']} {event['created_at']}")
    return "\n".join(lines).rstrip() + "\n"


def current_status() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        agents = [_row_to_dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY heartbeat_at DESC")]
        tasks = [_row_to_dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 10")]
        leases = [_row_to_dict(r) for r in conn.execute("SELECT * FROM leases WHERE state = 'active' ORDER BY acquired_at DESC")]
        messages = [_message_dict(r) for r in conn.execute("SELECT * FROM messages WHERE acked_at IS NULL ORDER BY created_at DESC LIMIT 10")]
        events = [_row_to_dict(r) for r in conn.execute("SELECT * FROM audit_events ORDER BY event_id DESC LIMIT 10")]
    return {
        "version": __version__,
        "agents": agents,
        "tasks": tasks,
        "active_leases": leases,
        "unread_messages": messages,
        "recent_events": events,
    }


def status() -> dict[str, Any]:
    return current_status()


def sync_board() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        agents = [_row_to_dict(r) for r in conn.execute("SELECT * FROM agents")]
        tasks = [_row_to_dict(r) for r in conn.execute("SELECT * FROM tasks")]
        plans = [_row_to_dict(r) for r in conn.execute("SELECT * FROM plans")]
        messages = [_message_dict(r) for r in conn.execute("SELECT * FROM messages")]
        leases = [_row_to_dict(r) for r in conn.execute("SELECT * FROM leases")]
    for item in agents:
        board.publish_agent(item)
    for item in tasks:
        board.publish_task(item)
    for item in plans:
        board.publish_plan(item)
    for item in messages:
        board.publish_message(item)
    for item in leases:
        board.publish_lease(item)
    board.publish_status(current_status())
    return {
        "ok": True,
        "board": board.board_path(),
        "agents": len(agents),
        "tasks": len(tasks),
        "plans": len(plans),
        "messages": len(messages),
        "leases": len(leases),
    }


def run_wrapped(
    command: list[str],
    resource_id: str,
    mode: str = "write",
    ttl: str | None = None,
    reason: str | None = None,
    holder_agent_id: str | None = None,
) -> dict[str, Any]:
    lease = acquire_lease(resource_id, mode=mode, ttl=ttl, reason=reason, holder_agent_id=holder_agent_id)
    operation_id = make_id("op")
    cmd_text = " ".join(command)
    with connect() as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO operations(operation_id, lease_id, resource_id, mode, command, state, started_at)
            VALUES(?, ?, ?, ?, ?, 'running', ?)
            """,
            (operation_id, lease["lease_id"], resource_id, mode, cmd_text, utc_now()),
        )
        _audit(
            conn,
            "operation.started",
            {"operation_id": operation_id, "command": cmd_text, "lease_id": lease["lease_id"]},
            actor_agent_id=holder_agent_id,
            resource_id=resource_id,
        )
    try:
        proc = subprocess.run(command, text=True, capture_output=True)
    except BaseException as exc:
        exit_code = 127 if isinstance(exc, OSError) else None
        with connect() as conn, transaction(conn):
            conn.execute(
                "UPDATE operations SET state = 'failed', exit_code = ?, completed_at = ? WHERE operation_id = ?",
                (exit_code, utc_now(), operation_id),
            )
            _audit(
                conn,
                "operation.failed",
                {
                    "operation_id": operation_id,
                    "exit_code": exit_code,
                    "error_type": type(exc).__name__,
                },
                actor_agent_id=holder_agent_id,
                resource_id=resource_id,
            )
        if isinstance(exc, OSError):
            raise CommonsError(f"unable to start wrapped command: {exc}") from exc
        raise
    else:
        state = "completed" if proc.returncode == 0 else "failed"
        with connect() as conn, transaction(conn):
            conn.execute(
                "UPDATE operations SET state = ?, exit_code = ?, completed_at = ? WHERE operation_id = ?",
                (state, proc.returncode, utc_now(), operation_id),
            )
            _audit(
                conn,
                f"operation.{state}",
                {"operation_id": operation_id, "exit_code": proc.returncode},
                actor_agent_id=holder_agent_id,
                resource_id=resource_id,
            )
    finally:
        release_lease(
            lease["lease_id"],
            holder_agent_id=holder_agent_id,
            fencing_epoch=lease["fencing_epoch"],
        )
    return {
        "operation_id": operation_id,
        "lease": lease,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
