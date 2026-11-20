# ruff: noqa: E501
"""The local server: static files, health, streamed answers, and what it must never do (log message text)."""

import json
import threading

import pytest
import requests

from atlas.assistant import llm, server


@pytest.fixture(scope="module")
def srv():
    s = server.serve(0, verbose=True)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()
    s.server_close()


def events(resp):
    out = []
    for block in resp.text.split("\n\n"):
        if block.startswith("data:"):
            out.append(json.loads(block[5:]))
    return out


def test_static_pages_and_data_files(srv):
    r = requests.get(srv + "/ask.html", timeout=10)
    assert r.status_code == 200 and "text/html" in r.headers["Content-Type"] and "Openway Assistant" in r.text
    r = requests.get(srv + "/assistant/rules.json", timeout=10)
    assert (
        r.status_code == 200 and "application/json" in r.headers["Content-Type"] and "NEED_WORDS" in r.json()
    )
    assert requests.get(srv + "/", allow_redirects=False, timeout=10).headers["Location"] == "/ask.html"


def test_path_traversal_is_refused(srv):
    for bad in (
        "/../pyproject.toml",
        "/%2e%2e/pyproject.toml",
        "/assistant/../../pyproject.toml",
        "/..%2f..%2fREADME.md",
    ):
        r = requests.get(srv + bad, timeout=10)
        assert r.status_code in (404, 400), bad
        assert "[project]" not in r.text


def test_health_says_whether_a_model_is_there(srv):
    j = requests.get(srv + "/api/health", timeout=10).json()
    assert j["reachable"] is True and isinstance(j["model"], bool) and "models" in j


def test_ask_streams_events_in_order(srv):
    body = {
        "message": "Where is the closest accessible restroom near downtown?",
        "context": {"today": "2026-11-20"},
        "mode": "rules",
    }
    r = requests.post(srv + "/api/ask", json=body, timeout=30)
    assert r.status_code == 200 and r.headers["Content-Type"].startswith("text/event-stream")
    ev = events(r)
    assert ev[0]["type"] == "text" and ev[-1]["type"] == "done" and ev[-1]["verified"] is True
    assert any(e["type"] == "card" for e in ev)


def test_model_mode_without_a_model_falls_back_to_rules(srv, monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    r = requests.post(
        srv + "/api/ask",
        json={
            "message": "events this weekend in Oxford",
            "context": {"today": "2026-11-20"},
            "mode": "model",
        },
        timeout=30,
    )
    ev = events(r)
    assert ev[-1]["type"] == "done" and ev[0]["type"] == "text"


def test_bad_requests_get_plain_errors(srv):
    assert requests.post(srv + "/api/ask", data=b"{nope", timeout=10).status_code == 400
    assert requests.post(srv + "/api/ask", data=b"x" * (server.MAX_BODY + 1), timeout=30).status_code == 413
    ev = events(requests.post(srv + "/api/ask", json={"message": "x" * 700}, timeout=10))
    assert ev[0]["type"] == "error" and "too long" in ev[0]["message"]
    ev = events(requests.post(srv + "/api/ask", json={"message": ""}, timeout=10))
    assert ev[0]["type"] == "error"
    ev = events(
        requests.post(
            srv + "/api/ask", json={"message": "hi", "context": {"today": "not a date"}}, timeout=10
        )
    )
    assert ev[0]["type"] == "error"


def test_the_server_never_logs_message_text_or_coordinates(srv, capsys):
    secret = "my secret question about Elm Street"
    requests.post(
        srv + "/api/ask",
        json={
            "message": secret,
            "context": {"today": "2026-11-20", "location": [39.12345, -84.54321]},
            "mode": "rules",
        },
        timeout=30,
    )
    requests.get(srv + "/ask.html?q=" + secret.replace(" ", "+") + "&lat=39.12345", timeout=10)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "secret" not in text and "39.12345" not in text and "-84.54321" not in text
