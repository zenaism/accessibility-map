# ruff: noqa: E501
"""Local server for the Openway Assistant: static map files, the chat page, and the /api/ask endpoint.

    python -m atlas.assistant.server [--port 8002]     (or scripts/serve_assistant.sh)

* GET  /ask.html, /cincinnati.html, /assistant/*.json, ...   files from data/map
* GET  /api/health                                          {"reachable": true, "model": bool, ...}
* POST /api/ask {message, context, image?, mode?}           server-sent events (see engine.events)

Standard library only. Binds to 127.0.0.1. Privacy: the server NEVER logs message text, photos or
coordinates; the access log keeps only the method, path and status code.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from ..core import ROOT
from .engine import Engine, events
from .schema import Context, SchemaError

MAP_DIR = ROOT / "data/map"
MAX_BODY = 4_000_000  # a shrunk photo is well under 1 MB; refuse anything absurd
_lock = threading.Lock()  # one model call at a time: the machine has little memory


class State:
    engine: Engine | None = None
    model_engine: Engine | None = None

    @classmethod
    def rules(cls) -> Engine:
        if cls.engine is None:
            cls.engine = Engine()
        return cls.engine

    @classmethod
    def model(cls):
        from . import llm

        if cls.model_engine is None:
            cls.model_engine = Engine(planner=llm.model_planner, composer=llm.model_composer)
        return cls.model_engine


def sse(obj: dict) -> bytes:
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n"


def run_ask(body: dict):
    """Yield the events for one question. Never raises: errors become an `error` event in plain words."""
    try:
        message = str(body.get("message") or "").strip()
        ctx = Context.from_dict(body.get("context") or {})
        image = body.get("image")
        mode = body.get("mode") or "model"
        if image:
            from . import llm

            with _lock:
                text = llm.describe_photo(image, message)
            yield {"type": "text", "kind": "answer", "delta": text}
            yield {
                "type": "detail",
                "items": [
                    "This describes what is visible in your photo. It does not tell you whether a place is accessible."
                ],
            }
            yield {"type": "meta", "as_of": None, "notes": [], "plan": None, "engine": "vision"}
            yield {"type": "done", "verified": False, "removed": 0}
            return
        if not message:
            yield {"type": "error", "message": "Please type a question."}
            return
        if len(message) > 600:
            yield {"type": "error", "message": "That question is too long. Please shorten it."}
            return
        if mode == "model":
            from . import llm

            if llm.available():
                with _lock:
                    ans = State.model().answer(message, ctx)
            else:
                ans = State.rules().answer(message, ctx)
        else:
            ans = State.rules().answer(message, ctx)
        yield from events(ans)
    except SchemaError as e:
        yield {"type": "error", "message": f"I could not read that request: {e}"}
    except Exception:  # noqa: BLE001
        yield {"type": "error", "message": "Something went wrong while looking that up. Please try again."}


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenwayAssistant/1"

    def log_message(self, fmt, *args):  # method, path (no query) and status only; never a body
        return

    def log_request(self, code="-", size="-"):
        if getattr(self.server, "verbose", False):
            path = urlsplit(self.path).path
            print(f"{self.command} {path} {code}")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            from . import llm

            info = llm.health()
            self._send(200, json.dumps({"reachable": True, **info}).encode(), "application/json")
            return
        if path in ("", "/"):
            self._send(302, b"", "text/plain", {"Location": "/ask.html"})
            return
        rel = path.lstrip("/")
        target = (MAP_DIR / rel).resolve()
        if MAP_DIR.resolve() not in target.parents or not target.is_file():
            self._send(404, b"Not found", "text/plain")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "application/javascript"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/ask":
            self._send(404, b"Not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            self._send(413, b"Too large", "text/plain")
            return
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._send(400, b"Bad JSON", "text/plain")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for ev in run_ask(body):
                self.wfile.write(sse(ev))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page cancelled the question


def serve(port: int = 8002, verbose: bool = False) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    srv.verbose = verbose
    return srv


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8002)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    from . import llm
    from .page import build

    build()
    srv = serve(a.port, a.verbose)
    info = llm.health()
    print(
        f"Openway Assistant is running.\n  Chat page : http://localhost:{a.port}/ask.html\n  Cincinnati: http://localhost:{a.port}/cincinnati.html\n  Oxford    : http://localhost:{a.port}/oxford.html"
    )
    print(
        "  Local model:",
        "ready (" + ", ".join(info["models"]) + ")"
        if info["model"]
        else "not available (guided mode still works; start Ollama for the model)",
    )
    print("Press Ctrl+C to stop. The server does not log what you ask.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
