"""Minimal Commons daemon."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

from . import service
from .daemon_control import daemon_port
from .http_server import CommonsThreadingHTTPServer
from .paths import pid_path


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        if self.path == "/status":
            self._json(200, service.status())
            return
        if self.path.startswith("/events"):
            self._json(200, {"events": service.audit_recent(100)})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    service.initialize()
    pid_path().write_text(str(os.getpid()), encoding="utf-8")
    server = CommonsThreadingHTTPServer((host, port), Handler)
    print(f"commonsd listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    finally:
        pid_path().unlink(missing_ok=True)


def main() -> int:
    serve(port=daemon_port())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
