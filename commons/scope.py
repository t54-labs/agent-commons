"""Workspace scope resolution for Commons."""

from __future__ import annotations

import fnmatch
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .paths import config_path
from .service import CommonsError
from .util import infer_repo


VALID_MODES = {"remote", "local", "disabled"}


def workspace_root(workspace: str | None = None) -> Path:
    start = Path(workspace or ".").expanduser().resolve()
    repo = infer_repo(start)
    return Path(repo).resolve() if repo else start


def project_config_path(workspace: str | None = None) -> Path:
    return workspace_root(workspace) / ".commons" / "project.toml"


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise CommonsError(f"invalid TOML config: {path}")
    return data


def normalize_entry(entry: dict[str, Any], source: str, workspace: Path, path: Path | None = None) -> dict[str, Any]:
    mode = str(entry.get("mode") or "").strip().lower()
    if mode not in VALID_MODES:
        raise CommonsError(f"invalid Commons scope mode: {mode or '<empty>'}")
    result = {
        "mode": mode,
        "source": source,
        "workspace": str(workspace),
        "project_config": str(path) if path else None,
        "remote": entry.get("remote"),
        "project": entry.get("project"),
        "scope": entry.get("scope"),
        "needs_user_decision": False,
    }
    if mode == "remote":
        if not result["remote"] or not result["project"]:
            raise CommonsError("remote Commons scope requires remote and project")
        result["scope"] = result["scope"] or "work"
    elif mode == "local":
        result["scope"] = result["scope"] or "local"
    else:
        result["scope"] = result["scope"] or "disabled"
    return result


def git_remote_url(workspace: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(workspace), "config", "--get", "remote.origin.url"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    value = proc.stdout.strip()
    return value or None


def rule_matches(rule: dict[str, Any], workspace: Path, remote_url: str | None) -> bool:
    match_path = rule.get("match_path")
    if match_path:
        pattern = str(Path(str(match_path)).expanduser())
        workspace_values = {str(workspace)}
        if str(workspace).startswith("/private/var/"):
            workspace_values.add(str(workspace).replace("/private/var/", "/var/", 1))
        pattern_values = {pattern}
        if pattern.startswith("/private/var/"):
            pattern_values.add(pattern.replace("/private/var/", "/var/", 1))
        if pattern.startswith("/var/"):
            pattern_values.add(pattern.replace("/var/", "/private/var/", 1))
        if any(fnmatch.fnmatch(value, candidate) for value in workspace_values for candidate in pattern_values):
            return True
    match_git_remote = rule.get("match_git_remote")
    if match_git_remote and remote_url and fnmatch.fnmatch(remote_url, str(match_git_remote)):
        return True
    return False


def resolve(workspace: str | None = None) -> dict[str, Any]:
    root = workspace_root(workspace)
    project_path = project_config_path(str(root))
    if project_path.exists():
        data = read_toml(project_path)
        commons = data.get("commons")
        if not isinstance(commons, dict):
            raise CommonsError(f"missing [commons] section in {project_path}")
        return normalize_entry(commons, "project", root, project_path)

    global_config = config_path()
    data = read_toml(global_config)
    rules = data.get("workspace_rules", [])
    if isinstance(rules, list):
        remote_url = git_remote_url(root)
        for rule in rules:
            if isinstance(rule, dict) and rule_matches(rule, root, remote_url):
                return normalize_entry(rule, "global-rule", root, global_config)

    return {
        "mode": "unknown",
        "source": "default",
        "workspace": str(root),
        "project_config": str(project_path),
        "remote": None,
        "project": None,
        "scope": None,
        "needs_user_decision": True,
        "prompt": (
            "This workspace has no Commons scope. Ask the user whether it should be "
            "remote work, local-only, or disabled before registering with Commons."
        ),
    }


def render_project_config(mode: str, remote: str | None = None, project: str | None = None, scope: str | None = None) -> str:
    lines = ["[commons]", f"mode = {toml_string(mode)}"]
    if remote:
        lines.append(f"remote = {toml_string(remote)}")
    if project:
        lines.append(f"project = {toml_string(project)}")
    if scope:
        lines.append(f"scope = {toml_string(scope)}")
    return "\n".join(lines) + "\n"


def toml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def enroll(
    mode: str,
    workspace: str | None = None,
    remote: str | None = None,
    project: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in VALID_MODES:
        raise CommonsError(f"invalid Commons scope mode: {mode}")
    if mode == "remote" and (not remote or not project):
        raise CommonsError("remote Commons scope requires --remote and --project")
    path = project_config_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_project_config(mode, remote, project, scope), encoding="utf-8")
    return resolve(str(path.parent.parent))


def append_workspace_rule(config_text: str, rule: dict[str, Any]) -> str:
    lines = [config_text.rstrip(), "", "[[workspace_rules]]"]
    for key in ("match_path", "match_git_remote", "mode", "remote", "project", "scope"):
        value = rule.get(key)
        if value:
            lines.append(f"{key} = {toml_string(value)}")
    return "\n".join(line for line in lines if line is not None).lstrip() + "\n"


def add_rule(
    mode: str,
    match_path: str | None = None,
    match_git_remote: str | None = None,
    remote: str | None = None,
    project: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in VALID_MODES:
        raise CommonsError(f"invalid Commons scope mode: {mode}")
    if not match_path and not match_git_remote:
        raise CommonsError("workspace rule requires --match-path or --match-git-remote")
    if mode == "remote" and (not remote or not project):
        raise CommonsError("remote workspace rule requires --remote and --project")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    rule = {
        "match_path": match_path,
        "match_git_remote": match_git_remote,
        "mode": mode,
        "remote": remote,
        "project": project,
        "scope": scope,
    }
    path.write_text(append_workspace_rule(current, rule), encoding="utf-8")
    try:
        path.chmod(0o600)
    except PermissionError:
        pass
    return {"ok": True, "config": str(path), "rule": {k: v for k, v in rule.items() if v}}
