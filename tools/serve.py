#!/usr/bin/env python3
"""Local development server: the static front end, with the API proxied.

The front end is plain files served from ``frontend/`` and talks to a relative
``/api`` base (see the ``api-base`` meta tag on every page). That is exactly how
it is deployed -- static files on one host, Django on another -- but it means a
plain ``python -m http.server`` cannot answer ``/api`` and every account action
falls back to the offline demo.

This server makes the local setup work end to end:

* static files from ``frontend/`` (no directory listings, ``no-store`` on HTML)
* ``/api/*`` forwarded verbatim to Django, method, headers, body and status
  included, so JWTs, DRF errors and throttling behave exactly as in production
* same origin, so there is no CORS preflight and no cookie/JWT split

Usage::

    # terminal 1
    cd backend && python manage.py runserver 127.0.0.1:8000

    # terminal 2
    python3 tools/serve.py --port 8080

    # or point at a different API, e.g. a staging deploy
    API_ORIGIN=https://api.example.com python3 tools/serve.py --port 8080

Only the standard library is used; this file is a developer convenience and is
never shipped to the browser.
"""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import os
import pathlib
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DEFAULT_API = os.environ.get("API_ORIGIN", "http://127.0.0.1:8000")

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class Handler(SimpleHTTPRequestHandler):
    """Static files for everything, a transparent proxy for ``/api``."""

    api_origin: str = DEFAULT_API
    verbose = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    # -- helpers -------------------------------------------------------

    def _is_api(self) -> bool:
        path = self.path.split("?", 1)[0]
        return path == "/api" or path.startswith("/api/")

    def _read_body(self) -> bytes | None:
        raw = self.headers.get("Content-Length")
        if not raw:
            return None
        try:
            length = int(raw)
        except ValueError:
            return None
        return self.rfile.read(length) if length else b""

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- proxy ---------------------------------------------------------

    def _proxy(self) -> None:
        parsed = urllib.parse.urlsplit(self.api_origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"detail": "API_ORIGIN is not a valid URL."})
            return

        body = self._read_body()
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() != "host"
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        headers.setdefault("X-Forwarded-Proto", "http")
        headers.setdefault("X-Forwarded-Host", self.headers.get("Host", "localhost"))

        connection_class = (
            http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(parsed.hostname, parsed.port, timeout=30)
        target = self.path
        try:
            connection.request(self.command, target, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
        except (OSError, http.client.HTTPException) as exc:
            self.log_error("API unreachable at %s: %s", self.api_origin, exc)
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "detail": "The API is not reachable. Start Django, or browse the static preview.",
                    "api_origin": self.api_origin,
                },
            )
            return
        finally:
            connection.close()

        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() in HOP_BY_HOP or key.lower() in {"content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    # -- HTTP verbs ----------------------------------------------------

    def do_GET(self):  # noqa: N802 - stdlib naming
        if self._is_api():
            return self._proxy()
        return super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        return super().do_HEAD()

    def do_POST(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_PUT(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_PATCH(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_DELETE(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_OPTIONS(self):  # noqa: N802
        if self._is_api():
            return self._proxy()
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, HEAD")
        self.end_headers()

    # -- responses -----------------------------------------------------

    def end_headers(self):
        already_set = any(
            b"cache-control" in line.lower() for line in getattr(self, "_headers_buffer", [])
        )
        if not already_set:
            path = self.path.split("?", 1)[0]
            if path.endswith(".html") or path in {"", "/"}:
                self.send_header("Cache-Control", "no-store")
            elif path.endswith((".css", ".js", ".webmanifest", ".svg", ".png")):
                self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def list_directory(self, path):  # noqa: D401 - never expose an index
        self.send_error(HTTPStatus.NOT_FOUND, "No directory listings")
        return None

    def log_message(self, fmt, *args):  # quieter, but still useful
        if self.verbose or "code 200" not in (fmt % args):
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="port (default 8080)")
    parser.add_argument(
        "--api",
        default=DEFAULT_API,
        help=f"origin of the Django API (default {DEFAULT_API}, or $API_ORIGIN)",
    )
    parser.add_argument("--verbose", action="store_true", help="log every request")
    args = parser.parse_args()

    if not FRONTEND.is_dir():
        parser.error(f"front end not found at {FRONTEND}")
    mimetypes.add_type("application/manifest+json", ".webmanifest")
    mimetypes.add_type("text/javascript", ".js")

    Handler.api_origin = args.api.rstrip("/")
    Handler.verbose = args.verbose
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"StudySpace dev server  http://{args.host}:{args.port}  →  {FRONTEND}")
    print(f"API proxy              /api/*  →  {Handler.api_origin}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
