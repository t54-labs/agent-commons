"""HTTP server primitives that avoid blocking reverse DNS lookups."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from socketserver import TCPServer


class CommonsThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with deterministic address binding."""

    daemon_threads = True

    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)
