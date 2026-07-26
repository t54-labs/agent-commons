"""Client helpers for Commons Private Relay."""

from __future__ import annotations

import json
import ipaddress
import os
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
from urllib.error import HTTPError, URLError

from . import __version__
from .paths import remote_config_path
from .service import CommonsError, PolicyDenied


class RemoteClientError(CommonsError):
    """A structured failure raised before or while calling a relay."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "remote_client_error",
        source: str = "commons-client",
        details: dict[str, Any] | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = source
        self.details = details or {}
        self.remediation = remediation


class RemotePolicyDenied(PolicyDenied):
    """A policy decision returned by Commons Relay."""

    def __init__(self, message: str, details: dict[str, Any], code: str = "policy_denied") -> None:
        super().__init__(message, details)
        self.code = code
        self.source = "commons-relay"
        self.remediation = details.get("remediation")


def open_request(req: Request, timeout: float = 10) -> Any:
    hostname = urlparse(req.full_url).hostname
    is_loopback = hostname == "localhost"
    if hostname and not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
    if is_loopback:
        return build_opener(ProxyHandler({})).open(req, timeout=timeout)
    return urlopen(req, timeout=timeout)


def ensure_remote_config_dir() -> None:
    path = remote_config_path().parent
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except PermissionError:
        pass


def load_config() -> dict[str, Any]:
    ensure_remote_config_dir()
    path = remote_config_path()
    if not path.exists():
        return {"remotes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CommonsError(f"invalid remote config: {path}") from exc
    if not isinstance(data, dict):
        raise CommonsError(f"invalid remote config: {path}")
    data.setdefault("remotes", {})
    return data


def save_config(config: dict[str, Any]) -> None:
    ensure_remote_config_dir()
    path = remote_config_path()
    path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    try:
        path.chmod(0o600)
    except PermissionError:
        pass


def add_remote(
    name: str,
    url: str,
    token_env: str = "COMMONS_RELAY_TOKEN",
    project: str | None = None,
    token_file: str | None = None,
) -> dict[str, Any]:
    if not name:
        raise CommonsError("remote name is required")
    if not url:
        raise CommonsError("remote url is required")
    config = load_config()
    config["remotes"][name] = {"url": url.rstrip("/"), "token_env": token_env}
    if project:
        config["remotes"][name]["project"] = project
    if token_file:
        config["remotes"][name]["token_file"] = str(Path(token_file).expanduser())
    save_config(config)
    return {
        "ok": True,
        "name": name,
        "url": url.rstrip("/"),
        "token_env": token_env,
        "token_file": config["remotes"][name].get("token_file"),
        "project": project,
    }


def get_remote(name: str = "default") -> dict[str, Any]:
    config = load_config()
    remote = config.get("remotes", {}).get(name)
    if not remote:
        raise CommonsError(f"unknown remote: {name}")
    return dict(remote)


def token_for(remote: dict[str, Any]) -> str:
    token_env = remote.get("token_env") or "COMMONS_RELAY_TOKEN"
    token = os.environ.get(token_env)
    if token:
        return token
    token_file = remote.get("token_file")
    if token_file:
        path = Path(str(token_file)).expanduser()
        try:
            metadata = path.stat()
        except OSError as exc:
            raise CommonsError(f"relay token file cannot be read: {path}") from exc
        if os.name != "nt" and metadata.st_mode & 0o077:
            raise RemoteClientError(
                f"relay token file permissions are too broad: {path}",
                code="relay_token_permissions_unsafe",
                details={"token_file": str(path), "mode": oct(metadata.st_mode & 0o777)},
                remediation=f'chmod 600 "{path}"',
            )
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CommonsError(f"relay token file cannot be read: {path}") from exc
        if token:
            return token
    raise RemoteClientError(
        f"relay token is not available; set {token_env} or configure a token file",
        code="relay_token_unavailable",
        remediation=f"Set {token_env} or configure --token-file for this remote.",
    )


def request(
    remote_name: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    require_auth: bool = True,
    project: str | None = None,
) -> Any:
    remote = get_remote(remote_name)
    request_payload = dict(payload) if payload is not None else None
    request_query = dict(query) if query is not None else {}
    headers = {"Accept": "application/json", "User-Agent": f"Commons/{__version__}"}
    if project is not None:
        resolved_project = project_arg(remote_name, project)
        headers["X-Commons-Project"] = resolved_project
        if method.upper() in {"POST", "PUT", "PATCH"}:
            request_payload = request_payload or {}
            embedded_project = request_payload.get("project_id")
            if embedded_project not in {None, "", resolved_project}:
                raise RemoteClientError(
                    "project context does not match the request payload",
                    code="project_context_mismatch",
                    details={"project": resolved_project, "payload_project_id": embedded_project},
                    remediation="Use one --project value for the entire command.",
                )
            request_payload["project_id"] = resolved_project
        else:
            embedded_project = request_query.get("project_id")
            if embedded_project not in {None, "", resolved_project}:
                raise RemoteClientError(
                    "project context does not match the request query",
                    code="project_context_mismatch",
                    details={"project": resolved_project, "query_project_id": embedded_project},
                    remediation="Use one --project value for the entire command.",
                )
            request_query["project_id"] = resolved_project
    url = remote["url"].rstrip("/") + path
    if request_query:
        url += "?" + urlencode({key: value for key, value in request_query.items() if value is not None})
    body = None
    if request_payload is not None:
        body = json.dumps(request_payload, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if require_auth:
        headers["Authorization"] = f"Bearer {token_for(remote)}"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with open_request(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {"error": data or exc.reason}
        error_code = payload.get("error_code") or f"relay_http_{exc.code}"
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        remediation = payload.get("remediation")
        if remediation:
            details.setdefault("remediation", remediation)
        if exc.code == 409:
            raise RemotePolicyDenied(payload.get("error", "relay policy denied"), details or payload, error_code) from exc
        raise RemoteClientError(
            payload.get("error") or f"relay http error {exc.code}",
            code=error_code,
            source=payload.get("error_source") or "commons-relay",
            details=details,
            remediation=remediation,
        ) from exc
    except URLError as exc:
        raise RemoteClientError(
            f"relay connection failed: {exc}",
            code="relay_connection_failed",
            remediation="Check the relay URL, DNS, TLS, and network reachability.",
        ) from exc


def status(remote_name: str = "default", project: str | None = None) -> dict[str, Any]:
    remote = get_remote(remote_name)
    health = request(remote_name, "GET", "/health", require_auth=False)
    resolved_project = project_arg(remote_name, project)
    try:
        authenticated = request(remote_name, "GET", "/v1/status", project=resolved_project)
        legacy_protocol = False
    except RemoteClientError as exc:
        if exc.code != "relay_http_404":
            raise
        request(remote_name, "GET", "/v1/agents", project=resolved_project)
        authenticated = {"ok": True, "project_id": resolved_project, "protocol_version": "legacy"}
        legacy_protocol = True
    return {
        "ok": bool(health.get("ok") and authenticated.get("ok")),
        "remote": remote_name,
        "url": remote["url"],
        "project": resolved_project,
        "auth_ready": True,
        "legacy_protocol": legacy_protocol,
        "health": health,
        "authenticated": authenticated,
    }


def project_arg(remote_name: str, project: str | None) -> str:
    if project:
        return project
    try:
        from . import scope as scope_config

        resolved_scope = scope_config.resolve(str(Path.cwd()))
    except (CommonsError, OSError, ValueError):
        resolved_scope = {}
    if resolved_scope.get("mode") == "remote" and resolved_scope.get("project"):
        scope_remote = resolved_scope.get("remote")
        if not scope_remote or scope_remote == remote_name:
            return str(resolved_scope["project"])
    remote = get_remote(remote_name)
    if remote.get("project"):
        return str(remote["project"])
    raise RemoteClientError(
        "project is required; pass --project or set a default project on the remote",
        code="project_context_required",
        remediation=(
            "Pass --project <project>, enroll this workspace with a remote project, "
            "or configure a default with commons remote add --project <project>."
        ),
    )


def register_agent(remote_name: str, project: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request(remote_name, "POST", "/v1/agents/register", payload, project=project)


def list_agents(remote_name: str, project: str) -> list[dict[str, Any]]:
    return request(remote_name, "GET", "/v1/agents", project=project)


def heartbeat_agent(remote_name: str, project: str, agent_id: str, status: str = "online") -> dict[str, Any]:
    return request(
        remote_name,
        "POST",
        "/v1/agents/heartbeat",
        {"agent_id": agent_id, "status": status},
        project=project,
    )


def send_message(remote_name: str, project: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request(remote_name, "POST", "/v1/messages", payload, project=project)


def inbox(
    remote_name: str,
    project: str,
    agent_id: str,
    unread_only: bool = False,
    limit: int = 50,
    cursor: str | None = None,
    before_message_id: str | None = None,
) -> dict[str, Any]:
    requested_limit = max(1, int(limit))
    messages: list[dict[str, Any]] = []
    next_cursor = cursor
    first_before = before_message_id
    pages_fetched = 0
    last_page: dict[str, Any] = {
        "server_limit": 200,
        "has_more": False,
        "window_complete": True,
        "next_cursor": None,
    }
    while len(messages) < requested_limit:
        page = request(
            remote_name,
            "GET",
            "/v1/inbox",
            query={
                "agent_id": agent_id,
                "unread_only": str(unread_only).lower(),
                "limit": requested_limit - len(messages),
                "cursor": next_cursor,
                "before": first_before,
                "envelope": "true",
            },
            project=project,
        )
        pages_fetched += 1
        if isinstance(page, list):
            legacy_count = len(page)
            page = {
                "messages": page,
                "page": {
                    "server_limit": legacy_count,
                    "has_more": None,
                    "window_complete": legacy_count == 0,
                    "truncated": True if requested_limit > legacy_count and legacy_count >= 200 else None,
                    "completeness": "complete_empty" if legacy_count == 0 else "unknown_legacy",
                    "legacy_response": True,
                    "next_cursor": None,
                },
            }
        page_messages = page.get("messages") or []
        messages.extend(page_messages[: requested_limit - len(messages)])
        last_page = page.get("page") or last_page
        next_cursor = last_page.get("next_cursor")
        first_before = None
        if not last_page.get("has_more") or not next_cursor or not page_messages:
            break
    legacy_unknown = last_page.get("completeness") == "unknown_legacy"
    has_more = bool(last_page.get("has_more")) if last_page.get("has_more") is not None else None
    return {
        "messages": messages,
        "page": {
            "requested_limit": requested_limit,
            "returned_count": len(messages),
            "server_limit": int(last_page.get("server_limit") or 200),
            "pages_fetched": pages_fetched,
            "has_more": has_more,
            "window_complete": False if legacy_unknown else not bool(has_more),
            "truncated": last_page.get("truncated") if legacy_unknown else bool(has_more),
            "next_cursor": next_cursor if next_cursor else None,
            "completeness": last_page.get("completeness", "complete" if not has_more else "partial"),
            "legacy_response": bool(last_page.get("legacy_response")),
        },
    }


def get_message(remote_name: str, project: str, message_id: str, agent_id: str) -> dict[str, Any]:
    return request(
        remote_name,
        "GET",
        f"/v1/messages/{message_id}",
        query={"agent_id": agent_id},
        project=project,
    )


def ack_message(remote_name: str, project: str, message_id: str, agent_id: str | None = None) -> dict[str, Any]:
    return request(remote_name, "POST", f"/v1/messages/{message_id}/ack", {"agent_id": agent_id}, project=project)


def acquire_lease(remote_name: str, project: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return request(remote_name, "POST", "/v1/leases/acquire", payload, project=project)
    except RemotePolicyDenied as exc:
        holder_agent_id = exc.details.get("holder_agent_id")
        if not holder_agent_id:
            raise
        details = dict(exc.details)
        holder_handle = details.get("holder_handle")
        recipient = f"@{holder_handle}" if holder_handle else str(holder_agent_id)
        resource_id = str(details.get("resource_id") or payload.get("resource_id") or "the resource")
        requester = str(payload.get("holder_agent_id") or "")
        details["coordination_recipient"] = recipient
        details["safe_next_actions"] = [
            shlex.join(
                [
                    "commons",
                    "remote",
                    "msg",
                    "send",
                    recipient,
                    f"Can you release {resource_id} when done?",
                    "--remote",
                    remote_name,
                    "--project",
                    project,
                    "--sender",
                    requester,
                ]
            ),
            shlex.join(
                [
                    "commons",
                    "remote",
                    "lease",
                    "list",
                    "--remote",
                    remote_name,
                    "--project",
                    project,
                    "--active",
                ]
            ),
        ]
        raise RemotePolicyDenied(str(exc), details, exc.code) from exc


def list_leases(remote_name: str, project: str, active: bool = False) -> list[dict[str, Any]]:
    return request(remote_name, "GET", "/v1/leases", query={"active": str(active).lower()}, project=project)


def release_lease(
    remote_name: str,
    project: str,
    lease_id: str,
    holder_agent_id: str,
    fencing_epoch: int,
) -> dict[str, Any]:
    return request(
        remote_name,
        "POST",
        f"/v1/leases/{lease_id}/release",
        {"holder_agent_id": holder_agent_id, "fencing_epoch": fencing_epoch},
        project=project,
    )


def create_task(remote_name: str, project: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request(remote_name, "POST", "/v1/tasks", payload, project=project)


def update_task(remote_name: str, project: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request(remote_name, "PATCH", f"/v1/tasks/{task_id}", payload, project=project)


def list_tasks(
    remote_name: str,
    project: str,
    status: str | None = None,
    owner_agent_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return request(
        remote_name,
        "GET",
        "/v1/tasks",
        query={"status": status, "owner_agent_id": owner_agent_id, "limit": limit},
        project=project,
    )


def get_task(remote_name: str, project: str, task_id: str) -> dict[str, Any]:
    return request(remote_name, "GET", f"/v1/tasks/{task_id}", project=project)


def config_path() -> Path:
    return remote_config_path()
