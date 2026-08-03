"""Commons command-line interface."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from . import board
from . import service
from . import daemon_control
from . import identity
from . import remote
from .util import hostname


REMOTE_TASK_STATUSES = [
    "created",
    "claimed",
    "in_progress",
    "blocked",
    "needs_human",
    "ready_for_review",
    "completed",
    "cancelled",
    "failed",
]


def normalize_argv(argv: list[str] | None) -> tuple[list[str], bool]:
    raw = list(sys.argv[1:] if argv is None else argv)
    normalized: list[str] = []
    json_requested = False
    iterator = iter(raw)
    for item in iterator:
        if item == "--":
            normalized.append(item)
            normalized.extend(iterator)
            break
        if item == "--json":
            json_requested = True
            continue
        normalized.append(item)
    return normalized, json_requested


def emit(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
    elif isinstance(value, str):
        print(value)
    else:
        print(humanize(value))


def humanize(value: Any) -> str:
    if isinstance(value, dict):
        if "messages" in value and "page" in value:
            page = value["page"]
            lines = [
                f"Inbox: {page.get('returned_count', len(value['messages']))} messages "
                f"(complete={page.get('window_complete')}, pages={page.get('pages_fetched', 1)})"
            ]
            for message in value["messages"]:
                lines.append(
                    f"  - {message['message_id']} from {message.get('sender_agent_id') or 'unknown'}: "
                    f"{message['body'][:100]}"
                )
            if page.get("next_cursor"):
                lines.append(f"Next cursor: {page['next_cursor']}")
            return "\n".join(lines)
        if {"agents", "tasks", "active_leases", "unread_messages"}.issubset(value.keys()):
            lines = ["Commons status", ""]
            lines.append(f"Agents: {len(value['agents'])}")
            for agent in value["agents"][:8]:
                label = agent.get("name") or agent["agent_id"]
                lines.append(f"  - {label} [{agent['runtime']}] {agent['status']} {agent.get('workspace') or ''}")
            lines.append("")
            lines.append(f"Active leases: {len(value['active_leases'])}")
            for lease in value["active_leases"][:8]:
                lines.append(
                    f"  - {lease['resource_id']} {lease['mode']} by {lease.get('holder_agent_id') or 'unknown'} "
                    f"(lease={lease['lease_id']}, epoch={lease['fencing_epoch']})"
                )
            lines.append("")
            lines.append(f"Unread messages: {len(value['unread_messages'])}")
            for msg in value["unread_messages"][:8]:
                lines.append(f"  - {msg['message_id']} from {msg.get('sender_agent_id')}: {msg['body'][:100]}")
            lines.append("")
            lines.append(f"Recent tasks: {len(value['tasks'])}")
            for task in value["tasks"][:8]:
                lines.append(f"  - {task['task_id']} [{task['status']}] {task['title']}")
            return "\n".join(lines)
        if "conflicts" in value:
            if value["conflicts"]:
                lines = [f"Conflicts for {value['resource_id']} ({value['mode']}):"]
                for c in value["conflicts"]:
                    lines.append(
                        f"  - held by {c.get('holder_agent_id') or 'unknown'} as {c['mode']} "
                        f"(lease={c['lease_id']}, epoch={c['fencing_epoch']})"
                    )
                return "\n".join(lines)
            return f"No conflicts for {value['resource_id']} ({value['mode']})"
        if value.get("ok") is True:
            return "ok"
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def summary_arg(args: argparse.Namespace) -> str | None:
    if getattr(args, "summary_file", None):
        return Path(args.summary_file).read_text(encoding="utf-8")
    return getattr(args, "summary", None) or getattr(args, "reason", None)


def body_arg(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    if getattr(args, "body", None) is not None:
        return args.body
    raise service.CommonsError("message body requires a positional body or --file")


def remote_workspace_arg(workspace: str | None, share_path: bool = False) -> tuple[str | None, bool]:
    if not workspace:
        return None, False
    path = Path(workspace).expanduser()
    if path.is_absolute() and not share_path:
        return path.name or "workspace", True
    return workspace, False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="commons")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version")

    sub.add_parser("init")
    sub.add_parser("up")

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--fix", action="store_true")
    doctor.add_argument("--project-dir")

    install_skill = sub.add_parser("install-skill")
    install_skill.add_argument("--target", choices=["codex", "claude", "both"], default="both")
    install_skill.add_argument("--scope", choices=["user", "project"], default="user")
    install_skill.add_argument("--project-dir")

    user_cmd = sub.add_parser("user")
    user_sub = user_cmd.add_subparsers(dest="user_cmd", required=True)
    user_sub.add_parser("show")
    user_set = user_sub.add_parser("set")
    user_set.add_argument("--name", required=True)

    scope_cmd = sub.add_parser("scope")
    scope_sub = scope_cmd.add_subparsers(dest="scope_cmd", required=True)
    scope_resolve = scope_sub.add_parser("resolve")
    scope_resolve.add_argument("--workspace")
    scope_enroll = scope_sub.add_parser("enroll")
    scope_enroll.add_argument("--workspace")
    scope_enroll.add_argument("--mode", choices=["remote", "local", "disabled"], required=True)
    scope_enroll.add_argument("--remote")
    scope_enroll.add_argument("--project")
    scope_enroll.add_argument("--scope")
    scope_rule = scope_sub.add_parser("rule")
    scope_rule_sub = scope_rule.add_subparsers(dest="scope_rule_cmd", required=True)
    scope_rule_add = scope_rule_sub.add_parser("add")
    scope_rule_add.add_argument("--match-path")
    scope_rule_add.add_argument("--match-git-remote")
    scope_rule_add.add_argument("--mode", choices=["remote", "local", "disabled"], required=True)
    scope_rule_add.add_argument("--remote")
    scope_rule_add.add_argument("--project")
    scope_rule_add.add_argument("--scope")

    status = sub.add_parser("status")
    status.add_argument("--watch", action="store_true")
    status.add_argument("--interval", type=float, default=2.0)
    watch = sub.add_parser("watch")
    watch.add_argument("--once", action="store_true")
    watch.add_argument("--interval", type=float, default=2.0)

    board_cmd = sub.add_parser("board")
    board_sub = board_cmd.add_subparsers(dest="board_cmd", required=True)
    board_sub.add_parser("path")
    board_sub.add_parser("sync")

    daemon = sub.add_parser("daemon")
    daemon_sub = daemon.add_subparsers(dest="daemon_cmd", required=True)
    daemon_sub.add_parser("status")
    start = daemon_sub.add_parser("start")
    start.add_argument("--foreground", action="store_true")
    daemon_sub.add_parser("stop")
    logs = daemon_sub.add_parser("logs")
    logs.add_argument("--lines", type=int, default=100)

    relay_cmd = sub.add_parser("relay")
    relay_sub = relay_cmd.add_subparsers(dest="relay_cmd", required=True)
    relay_serve = relay_sub.add_parser("serve")
    relay_serve.add_argument("--host", default="127.0.0.1")
    relay_serve.add_argument("--port", type=int, default=8766)
    relay_serve.add_argument("--db")
    relay_serve.add_argument("--token")

    remote_cmd = sub.add_parser("remote")
    remote_sub = remote_cmd.add_subparsers(dest="remote_cmd", required=True)
    remote_add = remote_sub.add_parser("add")
    remote_add.add_argument("name")
    remote_add.add_argument("--url", required=True)
    remote_add.add_argument("--token-env", default="COMMONS_RELAY_TOKEN")
    remote_add.add_argument("--token-file")
    remote_add.add_argument("--project")
    remote_status = remote_sub.add_parser("status")
    remote_status.add_argument("--remote", default="default")
    remote_status.add_argument("--project")

    remote_agent = remote_sub.add_parser("agent")
    remote_agent_sub = remote_agent.add_subparsers(dest="remote_agent_cmd", required=True)
    remote_agent_register = remote_agent_sub.add_parser("register")
    remote_agent_register.add_argument("--remote", default="default")
    remote_agent_register.add_argument("--project")
    remote_agent_register.add_argument("--agent")
    remote_agent_register.add_argument("--runtime", default="custom")
    remote_agent_register.add_argument("--workspace")
    remote_agent_register.add_argument("--share-workspace-path", action="store_true")
    remote_agent_register.add_argument(
        "--device-name",
        help="Device label shown in the private Console (defaults to the local hostname)",
    )
    remote_agent_register.add_argument("--name")
    remote_agent_register.add_argument("--handle")
    remote_agent_register.add_argument("--contact-code")
    remote_agent_register.add_argument("--task")
    remote_agent_list = remote_agent_sub.add_parser("list")
    remote_agent_list.add_argument("--remote", default="default")
    remote_agent_list.add_argument("--project")
    remote_agent_heartbeat = remote_agent_sub.add_parser("heartbeat")
    remote_agent_heartbeat.add_argument("--remote", default="default")
    remote_agent_heartbeat.add_argument("--project")
    remote_agent_heartbeat.add_argument("--agent", required=True)
    remote_agent_heartbeat.add_argument("--status", default="online")

    remote_msg = remote_sub.add_parser("msg")
    remote_msg_sub = remote_msg.add_subparsers(dest="remote_msg_cmd", required=True)
    remote_msg_send = remote_msg_sub.add_parser("send")
    remote_msg_send.add_argument("recipient")
    remote_msg_send.add_argument("body", nargs="?")
    remote_msg_send.add_argument("--file")
    remote_msg_send.add_argument("--remote", default="default")
    remote_msg_send.add_argument("--project")
    remote_msg_send.add_argument("--sender", required=True)
    remote_msg_send.add_argument("--thread")
    remote_msg_send.add_argument("--type", default="note")
    remote_msg_broadcast = remote_msg_sub.add_parser("broadcast")
    remote_msg_broadcast.add_argument("body", nargs="?")
    remote_msg_broadcast.add_argument("--file")
    remote_msg_broadcast.add_argument("--remote", default="default")
    remote_msg_broadcast.add_argument("--project")
    remote_msg_broadcast.add_argument("--sender", required=True)
    remote_msg_broadcast.add_argument("--thread")
    remote_msg_broadcast.add_argument("--type", default="broadcast")
    remote_msg_inbox = remote_msg_sub.add_parser("inbox")
    remote_msg_inbox.add_argument("--remote", default="default")
    remote_msg_inbox.add_argument("--project")
    remote_msg_inbox.add_argument("--agent", required=True)
    remote_msg_inbox.add_argument("--unread-only", action="store_true")
    remote_msg_inbox.add_argument("--limit", type=int, default=50)
    remote_msg_inbox.add_argument("--cursor")
    remote_msg_inbox.add_argument("--before")
    remote_msg_inbox.add_argument("--items-only", action="store_true")
    remote_msg_get = remote_msg_sub.add_parser("get", aliases=["read"])
    remote_msg_get.add_argument("message_id")
    remote_msg_get.add_argument("--remote", default="default")
    remote_msg_get.add_argument("--project")
    remote_msg_get.add_argument("--agent", required=True)
    remote_msg_ack = remote_msg_sub.add_parser("ack")
    remote_msg_ack.add_argument("message_id")
    remote_msg_ack.add_argument("--remote", default="default")
    remote_msg_ack.add_argument("--project")
    remote_msg_ack.add_argument("--agent", required=True)
    remote_inbox = remote_sub.add_parser("inbox")
    remote_inbox.add_argument("--remote", default="default")
    remote_inbox.add_argument("--project")
    remote_inbox.add_argument("--agent", required=True)
    remote_inbox.add_argument("--unread-only", action="store_true")
    remote_inbox.add_argument("--limit", type=int, default=50)
    remote_inbox.add_argument("--cursor")
    remote_inbox.add_argument("--before")
    remote_inbox.add_argument("--items-only", action="store_true")

    remote_lease = remote_sub.add_parser("lease")
    remote_lease_sub = remote_lease.add_subparsers(dest="remote_lease_cmd", required=True)
    remote_lease_acquire = remote_lease_sub.add_parser("acquire")
    remote_lease_acquire.add_argument("resource")
    remote_lease_acquire.add_argument("--remote", default="default")
    remote_lease_acquire.add_argument("--project")
    remote_lease_acquire.add_argument("--mode", default="write")
    remote_lease_acquire.add_argument("--ttl", default="30m")
    remote_lease_acquire.add_argument("--reason")
    remote_lease_acquire.add_argument("--agent", required=True)
    remote_lease_list = remote_lease_sub.add_parser("list")
    remote_lease_list.add_argument("--remote", default="default")
    remote_lease_list.add_argument("--project")
    remote_lease_list.add_argument("--active", action="store_true")
    remote_lease_renew = remote_lease_sub.add_parser("renew")
    remote_lease_renew.add_argument("lease_id")
    remote_lease_renew.add_argument("--remote", default="default")
    remote_lease_renew.add_argument("--project")
    remote_lease_renew.add_argument("--ttl", default="30m")
    remote_lease_renew.add_argument("--agent", required=True)
    remote_lease_renew.add_argument(
        "--fencing-epoch",
        type=int,
        help="Exact epoch returned by acquire or lease list; required to reject stale holders.",
    )
    remote_lease_release = remote_lease_sub.add_parser("release")
    remote_lease_release.add_argument("lease_id")
    remote_lease_release.add_argument("--remote", default="default")
    remote_lease_release.add_argument("--project")
    remote_lease_release.add_argument("--agent", required=True)
    remote_lease_release.add_argument(
        "--fencing-epoch",
        type=int,
        help="Exact epoch returned by acquire or lease list; required to reject stale holders.",
    )

    remote_task = remote_sub.add_parser("task")
    remote_task_sub = remote_task.add_subparsers(dest="remote_task_cmd", required=True)
    remote_task_create = remote_task_sub.add_parser("create")
    remote_task_create.add_argument("title")
    remote_task_create.add_argument("--remote", default="default")
    remote_task_create.add_argument("--project")
    remote_task_create.add_argument("--owner")
    remote_task_create.add_argument("--summary")
    remote_task_create.add_argument("--status", choices=REMOTE_TASK_STATUSES, default="in_progress")
    remote_task_create.add_argument("--current-step")
    remote_task_create.add_argument("--next-step")
    remote_task_create.add_argument("--blocked-reason")
    remote_task_create.add_argument("--progress", type=int)
    remote_task_create.add_argument("--blocked-by", action="append", default=[])
    remote_task_update = remote_task_sub.add_parser("update")
    remote_task_update.add_argument("task_id")
    remote_task_update.add_argument("--remote", default="default")
    remote_task_update.add_argument("--project")
    remote_task_update.add_argument("--owner")
    remote_task_update.add_argument("--summary")
    remote_task_update.add_argument("--status", choices=REMOTE_TASK_STATUSES)
    remote_task_update.add_argument("--current-step")
    remote_task_update.add_argument("--next-step")
    remote_task_update.add_argument("--blocked-reason")
    remote_task_update.add_argument("--progress", type=int)
    remote_task_update.add_argument("--blocked-by", action="append")
    remote_task_update.add_argument("--expected-version", type=int)
    remote_task_list = remote_task_sub.add_parser("list")
    remote_task_list.add_argument("--remote", default="default")
    remote_task_list.add_argument("--project")
    remote_task_list.add_argument("--status", choices=REMOTE_TASK_STATUSES)
    remote_task_list.add_argument("--owner")
    remote_task_list.add_argument("--limit", type=int, default=100)
    remote_task_show = remote_task_sub.add_parser("show")
    remote_task_show.add_argument("task_id")
    remote_task_show.add_argument("--remote", default="default")
    remote_task_show.add_argument("--project")

    agent = sub.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="agent_cmd", required=True)
    reg = agent_sub.add_parser("register")
    reg.add_argument("--runtime", default="custom")
    reg.add_argument("--workspace", default=None)
    reg.add_argument("--name", default=None)
    reg.add_argument("--task", default=None)
    reg.add_argument("--runtime-version", default=None)
    hb = agent_sub.add_parser("heartbeat")
    hb.add_argument("--agent", required=True)
    hb.add_argument("--status")
    agent_sub.add_parser("list")
    agent_sub.add_parser("status")
    show_agent = agent_sub.add_parser("show")
    show_agent.add_argument("agent_id")
    unregister = agent_sub.add_parser("unregister")
    unregister.add_argument("agent_id")

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_cmd", required=True)
    create = task_sub.add_parser("create")
    create.add_argument("title")
    create.add_argument("--owner")
    upd = task_sub.add_parser("update")
    upd.add_argument("task_id")
    upd.add_argument("--status")
    upd.add_argument("--summary")
    upd.add_argument("--summary-file")
    upd.add_argument("--owner")
    for name, status_value in (
        ("claim", "claimed"),
        ("block", "blocked"),
        ("unblock", "claimed"),
        ("complete", "completed"),
        ("fail", "failed"),
        ("cancel", "cancelled"),
    ):
        cmd = task_sub.add_parser(name)
        cmd.add_argument("task_id")
        cmd.add_argument("--summary")
        cmd.add_argument("--summary-file")
        cmd.add_argument("--reason")
        cmd.set_defaults(task_status=status_value)
    task_sub.add_parser("list")
    show_task = task_sub.add_parser("show")
    show_task.add_argument("task_id")

    plan = sub.add_parser("plan")
    plan_sub = plan.add_subparsers(dest="plan_cmd", required=True)
    pub = plan_sub.add_parser("publish")
    pub.add_argument("--task", required=True)
    pub.add_argument("--summary")
    pub.add_argument("--file")
    pub.add_argument("--agent")
    show_plan = plan_sub.add_parser("show")
    show_plan.add_argument("--task", required=True)
    diff_plan = plan_sub.add_parser("diff")
    diff_plan.add_argument("--task", required=True)
    diff_plan.add_argument("--from", dest="from_version", type=int, required=True)
    diff_plan.add_argument("--to", dest="to_version", type=int, required=True)

    msg = sub.add_parser("msg")
    msg_sub = msg.add_subparsers(dest="msg_cmd", required=True)
    send = msg_sub.add_parser("send")
    send.add_argument("recipient")
    send.add_argument("body", nargs="?")
    send.add_argument("--file")
    send.add_argument("--sender")
    send.add_argument("--task")
    send.add_argument("--type", default="note")
    broadcast = msg_sub.add_parser("broadcast")
    broadcast.add_argument("body", nargs="?")
    broadcast.add_argument("--file")
    broadcast.add_argument("--resource")
    broadcast.add_argument("--sender")
    broadcast.add_argument("--task")
    broadcast.add_argument("--type", default="broadcast")
    inbox = msg_sub.add_parser("inbox")
    inbox.add_argument("--agent")
    read = msg_sub.add_parser("read")
    read.add_argument("message_id")
    reply = msg_sub.add_parser("reply")
    reply.add_argument("message_id")
    reply.add_argument("body")
    reply.add_argument("--sender")
    ack = msg_sub.add_parser("ack")
    ack.add_argument("message_id")

    top_inbox = sub.add_parser("inbox")
    top_inbox.add_argument("--agent")

    context = sub.add_parser("context")
    context_sub = context.add_subparsers(dest="context_cmd", required=True)
    context_pub = context_sub.add_parser("publish")
    context_pub.add_argument("--task", required=True)
    context_pub.add_argument("--summary")
    context_pub.add_argument("--summary-file")
    context_pub.add_argument("--agent")
    context_req = context_sub.add_parser("request")
    context_req.add_argument("recipient")
    context_req.add_argument("--task")
    context_req.add_argument("--reason", required=True)
    context_req.add_argument("--sender")
    context_show = context_sub.add_parser("show")
    context_show.add_argument("--task")

    lease = sub.add_parser("lease")
    lease_sub = lease.add_subparsers(dest="lease_cmd", required=True)
    acq = lease_sub.add_parser("acquire")
    acq.add_argument("resource")
    acq.add_argument("--mode", default="write")
    acq.add_argument("--ttl", default="30m")
    acq.add_argument("--reason")
    acq.add_argument("--agent")
    rel = lease_sub.add_parser("release")
    rel.add_argument("lease_id")
    rel.add_argument("--agent")
    rel.add_argument("--fencing-epoch", type=int)
    renew = lease_sub.add_parser("renew")
    renew.add_argument("lease_id")
    renew.add_argument("--ttl", default="30m")
    renew.add_argument("--agent")
    renew.add_argument("--fencing-epoch", type=int)
    force = lease_sub.add_parser("force-release")
    force.add_argument("lease_id")
    force.add_argument("--reason", required=True)
    force.add_argument("--agent")
    lease_list = lease_sub.add_parser("list")
    lease_list.add_argument("--active", action="store_true")
    active = lease_sub.add_parser("active")
    active.set_defaults(active_only=True)
    conflicts = lease_sub.add_parser("conflicts")
    conflicts.add_argument("resource")
    conflicts.add_argument("--mode", default="write")

    resource = sub.add_parser("resource")
    resource_sub = resource.add_subparsers(dest="resource_cmd", required=True)
    resource_sub.add_parser("list")
    resource_show = resource_sub.add_parser("show")
    resource_show.add_argument("resource_id")
    alias = resource_sub.add_parser("alias")
    alias_sub = alias.add_subparsers(dest="alias_cmd", required=True)
    alias_add = alias_sub.add_parser("add")
    alias_add.add_argument("alias")
    alias_add.add_argument("canonical_resource")

    artifact = sub.add_parser("artifact")
    artifact_sub = artifact.add_subparsers(dest="artifact_cmd", required=True)
    attach = artifact_sub.add_parser("attach")
    attach.add_argument("--task")
    attach.add_argument("--type", required=True)
    attach.add_argument("--path", required=True)
    attach.add_argument("--visibility", default="workspace")
    artifact_list = artifact_sub.add_parser("list")
    artifact_list.add_argument("--task")
    artifact_show = artifact_sub.add_parser("show")
    artifact_show.add_argument("artifact_id")

    audit = sub.add_parser("audit")
    audit_sub = audit.add_subparsers(dest="audit_cmd", required=True)
    recent = audit_sub.add_parser("recent")
    recent.add_argument("--limit", type=int, default=50)
    audit_sub.add_parser("verify")
    audit_task = audit_sub.add_parser("task")
    audit_task.add_argument("task_id")
    audit_task.add_argument("--limit", type=int, default=100)
    audit_resource = audit_sub.add_parser("resource")
    audit_resource.add_argument("resource_id")
    audit_resource.add_argument("--limit", type=int, default=100)

    export = sub.add_parser("export")
    export_sub = export.add_subparsers(dest="export_cmd", required=True)
    export_task = export_sub.add_parser("task")
    export_task.add_argument("task_id")
    export_task.add_argument("--format", choices=["markdown"], default="markdown")
    export_resource = export_sub.add_parser("resource")
    export_resource.add_argument("resource_id")
    export_resource.add_argument("--format", choices=["markdown"], default="markdown")

    run = sub.add_parser("run")
    run.add_argument("--resource", required=True)
    run.add_argument("--mode", default="write")
    run.add_argument("--ttl", default="30m")
    run.add_argument("--reason")
    run.add_argument("--agent")
    run.add_argument("command", nargs=argparse.REMAINDER)

    deploy = sub.add_parser("deploy")
    deploy_sub = deploy.add_subparsers(dest="deploy_cmd", required=True)
    staging = deploy_sub.add_parser("staging")
    staging.add_argument("--resource", required=True)
    staging.add_argument("--ttl", default="30m")
    staging.add_argument("--reason", default="staging deploy")
    staging.add_argument("--agent")
    staging.add_argument("command", nargs=argparse.REMAINDER)

    db = sub.add_parser("db")
    db_sub = db.add_subparsers(dest="db_cmd", required=True)
    migrate = db_sub.add_parser("migrate")
    migrate.add_argument("--resource", required=True)
    migrate.add_argument("--ttl", default="30m")
    migrate.add_argument("--reason", default="database migration")
    migrate.add_argument("--agent")
    migrate.add_argument("command", nargs=argparse.REMAINDER)

    git = sub.add_parser("git")
    git_sub = git.add_subparsers(dest="git_cmd", required=True)
    push = git_sub.add_parser("push")
    push.add_argument("--resource", required=True)
    push.add_argument("--ttl", default="15m")
    push.add_argument("--reason", default="git push")
    push.add_argument("--agent")
    push.add_argument("command", nargs=argparse.REMAINDER)

    browser = sub.add_parser("browser")
    browser_sub = browser.add_subparsers(dest="browser_cmd", required=True)
    claim = browser_sub.add_parser("claim")
    claim.add_argument("profile")
    claim.add_argument("--mode", default="exclusive")
    claim.add_argument("--ttl", default="20m")
    claim.add_argument("--reason", default="browser profile claim")
    claim.add_argument("--agent")

    server = sub.add_parser("server")
    server_sub = server.add_subparsers(dest="server_cmd", required=True)
    restart = server_sub.add_parser("restart")
    restart.add_argument("--resource", required=True)
    restart.add_argument("--ttl", default="10m")
    restart.add_argument("--reason", default="server restart")
    restart.add_argument("--agent")
    restart.add_argument("command", nargs=argparse.REMAINDER)

    test = sub.add_parser("test")
    test_sub = test.add_subparsers(dest="test_cmd", required=True)
    e2e = test_sub.add_parser("e2e")
    e2e.add_argument("--scenario", default="golden-path")
    e2e.add_argument("--agents", default="fake,fake")
    e2e.add_argument("--keep-artifacts", action="store_true")
    runtime = test_sub.add_parser("runtime")
    runtime_sub = runtime.add_subparsers(dest="runtime_cmd", required=True)
    runtime_prepare = runtime_sub.add_parser("prepare")
    runtime_prepare.add_argument("--scenario", default="skill-handshake")
    runtime_prepare.add_argument("--agents", default="codex,claude-code")
    runtime_prepare.add_argument("--project-dir")
    runtime_verify = runtime_sub.add_parser("verify")
    runtime_verify.add_argument("run_id")

    return p


def require_remote_fencing_epoch(args: argparse.Namespace, project: str) -> int:
    if args.fencing_epoch is not None:
        return int(args.fencing_epoch)
    list_command = shlex.join(
        [
            "commons",
            "remote",
            "lease",
            "list",
            "--remote",
            args.remote,
            "--project",
            project,
            "--active",
            "--json",
        ]
    )
    operation = str(args.remote_lease_cmd)
    raise remote.RemoteClientError(
        f"remote lease {operation} requires --fencing-epoch <epoch> for {args.lease_id}",
        code="fencing_epoch_required",
        details={
            "lease_id": args.lease_id,
            "operation": operation,
            "safe_next_actions": [list_command],
        },
        remediation=(
            f"Run `{list_command}`, find this lease, and pass its `fencing_epoch`. "
            "The epoch prevents a stale holder from renewing or releasing a newer lease."
        ),
    )


def command(args: argparse.Namespace) -> tuple[Any, int]:
    if args.cmd == "version":
        return {"version": __version__}, 0
    if args.cmd == "init":
        return service.initialize(), 0
    if args.cmd == "up":
        service.initialize()
        daemon = daemon_control.start_background()
        return {"ok": bool(daemon.get("ok")), "daemon": daemon, "status": service.status()}, (0 if daemon.get("ok") else 2)
    if args.cmd == "doctor":
        return service.doctor(args.fix, args.project_dir), 0
    if args.cmd == "install-skill":
        return service.install_skill(args.target, args.scope, args.project_dir), 0
    if args.cmd == "user":
        if args.user_cmd == "show":
            return identity.load_profile(), 0
        if args.user_cmd == "set":
            return identity.save_profile(args.name), 0
    if args.cmd == "scope":
        from . import scope as scope_config

        if args.scope_cmd == "resolve":
            return scope_config.resolve(args.workspace), 0
        if args.scope_cmd == "enroll":
            return scope_config.enroll(args.mode, args.workspace, args.remote, args.project, args.scope), 0
        if args.scope_cmd == "rule" and args.scope_rule_cmd == "add":
            return scope_config.add_rule(
                args.mode,
                args.match_path,
                args.match_git_remote,
                args.remote,
                args.project,
                args.scope,
            ), 0
    if args.cmd == "status":
        if args.watch:
            try:
                while True:
                    print("\033c", end="")
                    emit(service.status(), args.json)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                return {"ok": True}, 0
        return service.status(), 0
    if args.cmd == "watch":
        if args.once:
            return service.status(), 0
        try:
            while True:
                print("\033c", end="")
                emit(service.status(), args.json)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return {"ok": True}, 0
    if args.cmd == "board":
        if args.board_cmd == "path":
            return {"board": board.board_path()}, 0
        if args.board_cmd == "sync":
            return service.sync_board(), 0
    if args.cmd == "daemon":
        if args.daemon_cmd == "status":
            return daemon_control.status(), 0
        if args.daemon_cmd == "start":
            if args.foreground:
                from .daemon import serve

                serve(port=daemon_control.daemon_port())
                return {"ok": True}, 0
            result = daemon_control.start_background()
            return result, (0 if result.get("ok") else 2)
        if args.daemon_cmd == "stop":
            result = daemon_control.stop()
            return result, (0 if result.get("ok") else 2)
        if args.daemon_cmd == "logs":
            return daemon_control.logs(args.lines), 0
    if args.cmd == "relay":
        if args.relay_cmd == "serve":
            from .relay import serve

            serve(host=args.host, port=args.port, db=args.db, token=args.token)
            return {"ok": True}, 0
    if args.cmd == "remote":
        if args.remote_cmd == "add":
            return remote.add_remote(args.name, args.url, args.token_env, args.project, args.token_file), 0
        if args.remote_cmd == "status":
            return remote.status(args.remote, args.project), 0
        if args.remote_cmd == "agent":
            if args.remote_agent_cmd == "register":
                project = remote.project_arg(args.remote, args.project)
                workspace, workspace_redacted = remote_workspace_arg(args.workspace, args.share_workspace_path)
                profile = identity.require_profile()
                default_label = "-".join(
                    part
                    for part in (
                        args.runtime,
                        Path(workspace).name if workspace else None,
                        args.agent[-8:] if args.agent else None,
                    )
                    if part
                )
                handle = identity.qualify_handle(profile, args.handle or default_label)
                name = identity.qualify_name(profile, args.name or handle)
                payload = {
                    "agent_id": args.agent,
                    "runtime": args.runtime,
                    "host": args.device_name or hostname(),
                    "workspace": workspace,
                    "name": name,
                    "handle": handle,
                    "user_name": profile["name"],
                    "contact_code": args.contact_code,
                    "task_id": args.task,
                }
                result = remote.register_agent(args.remote, project, payload)
                result["workspace_path_redacted"] = workspace_redacted
                return result, 0
            if args.remote_agent_cmd == "list":
                project = remote.project_arg(args.remote, args.project)
                return remote.list_agents(args.remote, project), 0
            if args.remote_agent_cmd == "heartbeat":
                project = remote.project_arg(args.remote, args.project)
                return remote.heartbeat_agent(args.remote, project, args.agent, args.status), 0
        if args.remote_cmd == "msg":
            if args.remote_msg_cmd == "send":
                project = remote.project_arg(args.remote, args.project)
                payload = {
                    "sender_agent_id": args.sender,
                    "recipient": args.recipient,
                    "thread_id": args.thread,
                    "message_type": args.type,
                    "body": body_arg(args),
                }
                return remote.send_message(args.remote, project, payload), 0
            if args.remote_msg_cmd == "broadcast":
                project = remote.project_arg(args.remote, args.project)
                payload = {
                    "sender_agent_id": args.sender,
                    "recipient": "broadcast",
                    "thread_id": args.thread,
                    "message_type": args.type,
                    "body": body_arg(args),
                }
                return remote.send_message(args.remote, project, payload), 0
            if args.remote_msg_cmd == "inbox":
                project = remote.project_arg(args.remote, args.project)
                result = remote.inbox(
                    args.remote,
                    project,
                    args.agent,
                    args.unread_only,
                    args.limit,
                    args.cursor,
                    args.before,
                )
                return (result["messages"] if args.items_only else result), 0
            if args.remote_msg_cmd in {"get", "read"}:
                project = remote.project_arg(args.remote, args.project)
                return remote.get_message(args.remote, project, args.message_id, args.agent), 0
            if args.remote_msg_cmd == "ack":
                project = remote.project_arg(args.remote, args.project)
                return remote.ack_message(args.remote, project, args.message_id, args.agent), 0
        if args.remote_cmd == "inbox":
            project = remote.project_arg(args.remote, args.project)
            result = remote.inbox(
                args.remote,
                project,
                args.agent,
                args.unread_only,
                args.limit,
                args.cursor,
                args.before,
            )
            return (result["messages"] if args.items_only else result), 0
        if args.remote_cmd == "lease":
            if args.remote_lease_cmd == "acquire":
                project = remote.project_arg(args.remote, args.project)
                payload = {
                    "resource_id": args.resource,
                    "mode": args.mode,
                    "ttl": args.ttl,
                    "holder_agent_id": args.agent,
                    "reason": args.reason,
                }
                return remote.acquire_lease(args.remote, project, payload), 0
            if args.remote_lease_cmd == "list":
                project = remote.project_arg(args.remote, args.project)
                return remote.list_leases(args.remote, project, args.active), 0
            if args.remote_lease_cmd == "renew":
                project = remote.project_arg(args.remote, args.project)
                fencing_epoch = require_remote_fencing_epoch(args, project)
                return remote.renew_lease(
                    args.remote,
                    project,
                    args.lease_id,
                    args.agent,
                    fencing_epoch,
                    args.ttl,
                ), 0
            if args.remote_lease_cmd == "release":
                project = remote.project_arg(args.remote, args.project)
                fencing_epoch = require_remote_fencing_epoch(args, project)
                return remote.release_lease(
                    args.remote,
                    project,
                    args.lease_id,
                    args.agent,
                    fencing_epoch,
                ), 0
        if args.remote_cmd == "task":
            project = remote.project_arg(args.remote, args.project)
            if args.remote_task_cmd == "create":
                return remote.create_task(
                    args.remote,
                    project,
                    {
                        "title": args.title,
                        "owner_agent_id": args.owner,
                        "summary": args.summary,
                        "status": args.status,
                        "current_step": args.current_step,
                        "next_step": args.next_step,
                        "blocked_reason": args.blocked_reason,
                        "progress_percent": args.progress,
                        "blocked_by": args.blocked_by,
                    },
                ), 0
            if args.remote_task_cmd == "update":
                payload = {
                    key: value
                    for key, value in {
                        "owner_agent_id": args.owner,
                        "summary": args.summary,
                        "status": args.status,
                        "current_step": args.current_step,
                        "next_step": args.next_step,
                        "blocked_reason": args.blocked_reason,
                        "progress_percent": args.progress,
                        "blocked_by": args.blocked_by,
                        "expected_version": args.expected_version,
                    }.items()
                    if value is not None
                }
                return remote.update_task(args.remote, project, args.task_id, payload), 0
            if args.remote_task_cmd == "list":
                return remote.list_tasks(args.remote, project, args.status, args.owner, args.limit), 0
            if args.remote_task_cmd == "show":
                return remote.get_task(args.remote, project, args.task_id), 0
    if args.cmd == "agent":
        if args.agent_cmd == "register":
            profile = identity.require_profile()
            workspace_label = Path(args.workspace).name if args.workspace else Path.cwd().name
            qualified_name = identity.qualify_name(profile, args.name or f"{args.runtime}-{workspace_label}")
            result = service.register_agent(args.runtime, args.workspace, qualified_name, args.task, args.runtime_version)
            result.update({"name": qualified_name, "user_name": profile["name"], "user_slug": profile["slug"]})
            return result, 0
        if args.agent_cmd == "heartbeat":
            return service.heartbeat(args.agent, args.status), 0
        if args.agent_cmd == "list":
            return service.list_agents(), 0
        if args.agent_cmd == "status":
            return service.list_agents(), 0
        if args.agent_cmd == "show":
            rows = [a for a in service.list_agents() if a["agent_id"] == args.agent_id]
            return (rows[0] if rows else {"error": "not found"}), (0 if rows else 1)
        if args.agent_cmd == "unregister":
            return service.unregister_agent(args.agent_id), 0
    if args.cmd == "task":
        if args.task_cmd == "create":
            return service.create_task(args.title, args.owner), 0
        if args.task_cmd == "update":
            return service.update_task(args.task_id, args.status, summary_arg(args), args.owner), 0
        if args.task_cmd in {"claim", "block", "complete", "fail", "cancel"}:
            return service.update_task(args.task_id, args.task_status, summary_arg(args)), 0
        if args.task_cmd == "unblock":
            return service.update_task(args.task_id, args.task_status, summary_arg(args)), 0
        if args.task_cmd == "list":
            return service.list_tasks(), 0
        if args.task_cmd == "show":
            return service.get_task(args.task_id), 0
    if args.cmd == "plan":
        if args.plan_cmd == "publish":
            body = Path(args.file).read_text(encoding="utf-8") if args.file else None
            return service.publish_plan(args.task, args.summary, body, args.agent), 0
        if args.plan_cmd == "show":
            return service.show_plan(args.task), 0
        if args.plan_cmd == "diff":
            return service.diff_plan(args.task, args.from_version, args.to_version), 0
    if args.cmd == "msg":
        if args.msg_cmd == "send":
            recipient = args.recipient[1:] if args.recipient.startswith("@") else args.recipient
            return service.send_message(body_arg(args), args.sender, recipient, args.task, message_type=args.type), 0
        if args.msg_cmd == "broadcast":
            body = body_arg(args)
            if args.resource:
                body = f"[resource:{args.resource}] {body}"
            return service.send_message(body, args.sender, None, args.task, message_type=args.type), 0
        if args.msg_cmd == "inbox":
            return service.inbox(args.agent), 0
        if args.msg_cmd == "read":
            return service.read_message(args.message_id), 0
        if args.msg_cmd == "reply":
            return service.reply_message(args.message_id, args.body, args.sender), 0
        if args.msg_cmd == "ack":
            return service.ack_message(args.message_id), 0
    if args.cmd == "inbox":
        return service.inbox(args.agent), 0
    if args.cmd == "context":
        if args.context_cmd == "publish":
            summary = args.summary
            if args.summary_file:
                summary = Path(args.summary_file).read_text(encoding="utf-8")
            if not summary:
                return {"error": "context publish requires --summary or --summary-file"}, 2
            return service.publish_context(args.task, summary, args.agent), 0
        if args.context_cmd == "request":
            recipient = args.recipient[1:] if args.recipient.startswith("@") else args.recipient
            return service.request_context(recipient, args.task, args.reason, args.sender), 0
        if args.context_cmd == "show":
            messages = [m for m in service.inbox(None) if m.get("message_type") == "context"]
            if args.task:
                messages = [m for m in messages if m.get("task_id") == args.task]
            return messages, 0
    if args.cmd == "lease":
        if args.lease_cmd == "acquire":
            return service.acquire_lease(args.resource, args.mode, args.ttl, args.reason, args.agent), 0
        if args.lease_cmd == "release":
            return service.release_lease(args.lease_id, args.agent, args.fencing_epoch), 0
        if args.lease_cmd == "renew":
            return service.renew_lease(args.lease_id, args.ttl, args.agent, args.fencing_epoch), 0
        if args.lease_cmd == "force-release":
            return service.force_release_lease(args.lease_id, args.reason, args.agent), 0
        if args.lease_cmd == "list":
            return service.list_leases(bool(args.active)), 0
        if args.lease_cmd == "active":
            return service.list_leases(True), 0
        if args.lease_cmd == "conflicts":
            return service.lease_conflicts(args.resource, args.mode), 0
    if args.cmd == "resource":
        if args.resource_cmd == "list":
            return service.list_resources(), 0
        if args.resource_cmd == "show":
            return service.show_resource(args.resource_id), 0
        if args.resource_cmd == "alias" and args.alias_cmd == "add":
            return service.add_resource_alias(args.alias, args.canonical_resource), 0
    if args.cmd == "artifact":
        if args.artifact_cmd == "attach":
            return service.attach_artifact(args.task, args.type, args.path, args.visibility), 0
        if args.artifact_cmd == "list":
            return service.list_artifacts(args.task), 0
        if args.artifact_cmd == "show":
            return service.show_artifact(args.artifact_id), 0
    if args.cmd == "audit":
        if args.audit_cmd == "recent":
            return service.audit_recent(args.limit), 0
        if args.audit_cmd == "verify":
            return service.audit_verify(), 0
        if args.audit_cmd == "task":
            return service.audit_task(args.task_id, args.limit), 0
        if args.audit_cmd == "resource":
            return service.audit_resource(args.resource_id, args.limit), 0
    if args.cmd == "export":
        if args.export_cmd == "task":
            return service.export_task_markdown(args.task_id), 0
        if args.export_cmd == "resource":
            return service.export_resource_markdown(args.resource_id), 0
    if args.cmd == "run":
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            return {"error": "missing command after --"}, 2
        result = service.run_wrapped(command, args.resource, args.mode, args.ttl, args.reason, args.agent)
        return result, int(result["exit_code"])
    if args.cmd == "deploy" and args.deploy_cmd == "staging":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        if not command:
            return {"error": "missing deploy command after --"}, 2
        result = service.run_wrapped(command, args.resource, "exclusive", args.ttl, args.reason, args.agent)
        return result, int(result["exit_code"])
    if args.cmd == "db" and args.db_cmd == "migrate":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        if not command:
            return {"error": "missing migration command after --"}, 2
        result = service.run_wrapped(command, args.resource, "maintenance", args.ttl, args.reason, args.agent)
        return result, int(result["exit_code"])
    if args.cmd == "git" and args.git_cmd == "push":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        if not command:
            command = ["git", "push"]
        result = service.run_wrapped(command, args.resource, "write", args.ttl, args.reason, args.agent)
        return result, int(result["exit_code"])
    if args.cmd == "browser" and args.browser_cmd == "claim":
        resource = f"browser-profile:{args.profile}"
        return service.acquire_lease(resource, args.mode, args.ttl, args.reason, args.agent), 0
    if args.cmd == "server" and args.server_cmd == "restart":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        if not command:
            return {"error": "missing restart command after --"}, 2
        result = service.run_wrapped(command, args.resource, "exclusive", args.ttl, args.reason, args.agent)
        return result, int(result["exit_code"])
    if args.cmd == "test":
        if args.test_cmd == "e2e":
            from .test_runner import run_e2e

            return run_e2e(args.scenario, args.agents, args.keep_artifacts), 0
        if args.test_cmd == "runtime":
            if args.runtime_cmd == "prepare":
                return service.prepare_runtime_smoke(args.agents, args.scenario, args.project_dir), 0
            if args.runtime_cmd == "verify":
                return service.verify_runtime_smoke(args.run_id), 0
    return {"error": "unknown command"}, 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    normalized_argv, json_requested = normalize_argv(argv)
    args = parser.parse_args(normalized_argv)
    args.json = bool(args.json or json_requested)
    try:
        result, code = command(args)
    except service.PolicyDenied as exc:
        payload = {
            "error": str(exc),
            "error_code": getattr(exc, "code", "policy_denied"),
            "error_source": getattr(exc, "source", "commons-policy"),
            "details": exc.details,
        }
        remediation = getattr(exc, "remediation", None)
        if remediation:
            payload["remediation"] = remediation
        emit(payload, args.json)
        return 2
    except service.CommonsError as exc:
        payload = {
            "error": str(exc),
            "error_code": getattr(exc, "code", "commons_error"),
            "error_source": getattr(exc, "source", "commons-cli"),
        }
        details = getattr(exc, "details", None)
        remediation = getattr(exc, "remediation", None)
        if details:
            payload["details"] = details
        if remediation:
            payload["remediation"] = remediation
        emit(payload, args.json)
        return 1
    except Exception as exc:  # Keep CLI failures inspectable for agents.
        emit({"error": type(exc).__name__, "message": str(exc)}, args.json)
        return 1
    emit(result, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
