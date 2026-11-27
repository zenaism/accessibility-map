# ruff: noqa: E501
"""Local server for the Openway Assistant: static map files, the chat page, and the /api/ask endpoint.

    python -m atlas.assistant.server [--port 8002]     (or scripts/serve_assistant.sh)

* GET  /ask.html, /cincinnati.html, /assistant/*.json, ...   files from data/map
* GET  /api/health                                          {"reachable": true, "model": bool, ...}
* POST /api/ask {message, context, image?, mode?, history?}           server-sent events (see engine.events)

Standard library only. Binds to 127.0.0.1. Privacy: the server NEVER logs message text, photos or
coordinates; the access log keeps only the method, path and status code.

Shared server (see docs/hosted_backend.md): with OPENWAY_PROVIDER=openrouter the model is a hosted one.
Then OPENWAY_ALLOW_ORIGINS (comma-separated) names the pages on other sites that may call the API, and
OPENWAY_RATE_PER_HOUR (per visitor) and OPENWAY_RATE_PER_DAY (everyone) cap the model calls; over a cap,
the answer comes from guided mode instead, so nobody is left without one.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import time
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from ..core import ROOT
from .engine import Engine, events
from .schema import Context, SchemaError

MAP_DIR = ROOT / "data/map"
MAX_BODY = 4_000_000  # a shrunk photo is well under 1 MB; refuse anything absurd
_lock = threading.Lock()  # one LOCAL model call at a time: the machine has little memory
ALLOW_ORIGINS = {o.strip() for o in os.environ.get("OPENWAY_ALLOW_ORIGINS", "").split(",") if o.strip()}
RATE_PER_HOUR = int(os.environ.get("OPENWAY_RATE_PER_HOUR", "30"))  # model questions per visitor
RATE_PER_DAY = int(os.environ.get("OPENWAY_RATE_PER_DAY", "600"))  # model questions from everyone
HOSTED_NOTE = "The online model is busy, so I used guided mode instead."
_rate_lock = threading.Lock()
_rate: dict = {
    "day": "",
    "total": 0,
    "seen": {},
}  # visitor address -> recent times; memory only, never written


def model_lock():
    """A hosted model takes many questions at once; a local one takes one."""
    from . import llm

    return nullcontext() if llm.hosted() else _lock


def allow_model(client: str | None, now: float | None = None) -> bool:
    """May this visitor use the hosted model now? Counts the question when the answer is yes."""
    now = time.time() if now is None else now
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _rate_lock:
        if _rate["day"] != day:
            _rate.update(day=day, total=0, seen={})
        recent = [t for t in _rate["seen"].get(client or "?", []) if now - t < 3600]
        if _rate["total"] >= RATE_PER_DAY or len(recent) >= RATE_PER_HOUR:
            _rate["seen"][client or "?"] = recent
            return False
        _rate["seen"][client or "?"] = [*recent, now]
        _rate["total"] += 1
        return True


def _turns(history) -> list:
    """The earlier turns the page sent, cut down to what a model may see: a few short lines of text."""
    out = []
    for h in history if isinstance(history, list) else []:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("text"), str):
            out.append({"role": h["role"], "text": h["text"][:400]})
    return out[-6:]


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


def run_ask(body: dict, client: str | None = None):
    """Yield the events for one question. Never raises: errors become an `error` event in plain words.
    `client` is the visitor's address, used only to count hosted-model questions."""
    try:
        message = str(body.get("message") or "").strip()
        ctx = Context.from_dict(body.get("context") or {})
        image = body.get("image")
        mode = body.get("mode") or "model"
        if image:
            from . import llm

            with model_lock():
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

            if llm.available() and llm.hosted() and not allow_model(client):
                yield {"type": "note", "message": HOSTED_NOTE}
                ans = State.rules().answer(message, ctx)
            elif llm.available():
                with model_lock():
                    ans = State.model().answer(message, ctx, history=_turns(body.get("history")))
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

    def _cors(self):
        """Let the named pages on other sites call the API (the public page is not served from here)."""
        origin = self.headers.get("Origin")
        if origin and origin in ALLOW_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")

    def _client(self) -> str:
        """The visitor's address. A forwarding script on this machine passes the real one along."""
        addr = self.client_address[0]
        fwd = self.headers.get("X-Forwarded-For")
        if fwd and addr in ("127.0.0.1", "::1"):
            return fwd.split(",")[-1].strip() or addr
        return addr

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
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
        self._cors()
        self.end_headers()
        try:
            for ev in run_ask(body, self._client()):
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
    if info.get("hosted"):
        print(
            "  Online model:",
            "ready (" + ", ".join(info["models"]) + ")"
            if info["model"]
            else "no key found (guided mode still works; set OPENROUTER_API_KEY or OPENWAY_KEY_FILE)",
        )
    else:
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
