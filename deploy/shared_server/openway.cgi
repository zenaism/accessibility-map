#!/usr/bin/python3
"""Front door for the Openway Assistant on a shared web server (Apache user directory, CGI).

Copy to ~/public_html/cgi-bin/openway.cgi (mode 755). The web server runs this file as its own user, so it
holds no key and reads no project file: it only passes /api/health and /api/ask to the assistant server
that the project owner runs on this machine (deploy/shared_server/run.sh), and sends the reply back as it
arrives. Standard library only. Nothing is logged.

Page setting:  OPENWAY_SERVER_BASE=https://<host>/~<user>/cgi-bin/openway.cgi
"""

import os
import sys
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:18002"  # the port in run.sh
ROUTES = {"/api/health": ("GET", "OPTIONS"), "/api/ask": ("POST", "OPTIONS")}
MAX_BODY = 64_000  # a question and its context; photos are not accepted here
PASS_BACK = ("content-type", "cache-control", "vary")

out = sys.stdout.buffer


def reply(status: str, headers: list, body: bytes = b"") -> None:
    out.write(f"Status: {status}\r\n".encode())
    for k, v in headers:
        out.write(f"{k}: {v}\r\n".encode())
    out.write(b"\r\n" + body)
    out.flush()


def main() -> None:
    path = os.environ.get("PATH_INFO", "")
    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    if method not in ROUTES.get(path, ()):
        reply("404 Not Found", [("Content-Type", "text/plain")], b"Not found")
        return
    try:
        n = int(os.environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        n = 0
    if n > MAX_BODY:
        reply("413 Payload Too Large", [("Content-Type", "text/plain")], b"Too large")
        return
    data = sys.stdin.buffer.read(n) if n else None
    req = urllib.request.Request(BACKEND + path, data=data, method=method)
    for env, name in (
        ("HTTP_ORIGIN", "Origin"),
        ("CONTENT_TYPE", "Content-Type"),
        ("REMOTE_ADDR", "X-Forwarded-For"),
        ("HTTP_ACCESS_CONTROL_REQUEST_METHOD", "Access-Control-Request-Method"),
    ):
        if os.environ.get(env):
            req.add_header(name, os.environ[env])
    try:
        resp = urllib.request.urlopen(req, timeout=120)  # noqa: S310  fixed local address
    except urllib.error.HTTPError as e:
        resp = e  # pass the server's own error reply along
    except (urllib.error.URLError, OSError):
        reply(
            "503 Service Unavailable",
            [("Content-Type", "application/json"), ("Cache-Control", "no-store")],
            b'{"reachable": false}',
        )
        return
    headers = [
        (k, v)
        for k, v in resp.headers.items()
        if k.lower() in PASS_BACK or k.lower().startswith("access-control-")
    ]
    reply(f"{resp.status} {resp.reason}", headers)
    while True:
        chunk = resp.read1(65536)
        if not chunk:
            break
        out.write(chunk)
        out.flush()


main()
