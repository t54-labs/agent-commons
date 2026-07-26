"""Daemon lifecycle helpers."""

from __future__ import annotations

import http.client
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .paths import log_dir, pid_path


def daemon_port() -> int:
    return int(os.environ.get("COMMONS_DAEMON_PORT", "8765"))


def daemon_url(path: str = "/health") -> str:
    return f"http://127.0.0.1:{daemon_port()}{path}"


def read_pid() -> int | None:
    try:
        raw = pid_path().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return int(raw) if raw else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def health(timeout: float = 1.0) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", daemon_port(), timeout=timeout)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        response.read()
        return response.status == 200
    except (OSError, TimeoutError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def status() -> dict:
    pid = read_pid()
    return {
        "pid": pid,
        "pid_file": str(pid_path()),
        "pid_alive": bool(pid and pid_alive(pid)),
        "http_healthy": health(),
        "url": daemon_url("/health"),
    }


def logs(lines: int = 100) -> dict:
    path = log_dir() / "commonsd.log"
    if not path.exists():
        return {"ok": True, "path": str(path), "lines": []}
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"ok": True, "path": str(path), "lines": content[-lines:]}


def start_background() -> dict:
    current = status()
    if current["http_healthy"]:
        return {"ok": True, "already_running": True, **current}

    log_dir().mkdir(parents=True, exist_ok=True)
    log_path = log_dir() / "commonsd.log"
    out = log_path.open("ab")
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "commons.daemon"],
        stdout=out,
        stderr=out,
        stdin=subprocess.DEVNULL,
        cwd=root,
        env=env,
        start_new_session=True,
    )
    out.close()
    pid_path().write_text(str(proc.pid), encoding="utf-8")
    start_timeout = float(os.environ.get("COMMONS_DAEMON_START_TIMEOUT", "15"))
    deadline = time.monotonic() + max(1.0, start_timeout)
    while time.monotonic() < deadline:
        if health(timeout=0.25):
            return {"ok": True, "pid": proc.pid, "log": str(log_path), "url": daemon_url("/health")}
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    pid_path().unlink(missing_ok=True)
    return {
        "ok": False,
        "pid": proc.pid,
        "exit_code": proc.returncode,
        "log": str(log_path),
        "log_tail": logs(20)["lines"],
        "error": "daemon did not become healthy",
    }


def stop() -> dict:
    pid = read_pid()
    if not pid:
        return {"ok": True, "stopped": False, "message": "no pid file"}
    if not pid_alive(pid):
        pid_path().unlink(missing_ok=True)
        return {"ok": True, "stopped": False, "message": "pid was not alive"}
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if not pid_alive(pid):
            pid_path().unlink(missing_ok=True)
            return {"ok": True, "stopped": True, "pid": pid}
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    for _ in range(20):
        if not pid_alive(pid):
            pid_path().unlink(missing_ok=True)
            return {"ok": True, "stopped": True, "pid": pid, "killed": True}
        time.sleep(0.1)
    return {"ok": False, "stopped": False, "pid": pid, "error": "daemon did not stop"}
