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


# ---- shared server: a hosted model, pages on other sites, limits (docs/hosted_backend.md) ----
ASK = {"message": "where can I park near the zoo?", "context": {"today": "2026-11-20"}, "mode": "model"}


class FakeReply:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "choices": [{"message": {"content": self.content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }


def hosted(monkeypatch, replies):
    """Hosted mode with a fake model service; returns the list of requests it received."""
    sent = []
    real = requests.post

    def post(url, json=None, headers=None, timeout=None, **kw):
        if not url.startswith(llm.OPENROUTER):  # the test's own calls to the local server
            return real(url, json=json, headers=headers, timeout=timeout, **kw)
        sent.append({"url": url, "json": json, "headers": headers})
        return FakeReply(replies(json))

    monkeypatch.setattr(llm, "PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(server, "_rate", {"day": "", "total": 0, "seen": {}})
    return sent


def test_hosted_health_needs_only_a_key(srv, monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENWAY_KEY_FILE", raising=False)
    j = requests.get(srv + "/api/health", timeout=10).json()
    assert j["hosted"] is True and j["model"] is False and j["vision"] is False
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    j = requests.get(srv + "/api/health", timeout=10).json()
    assert j["model"] is True and j["models"] == [llm.CLOUD_MODEL] and "test-key" not in json.dumps(j)


def test_key_can_come_from_a_private_file(tmp_path, monkeypatch):
    f = tmp_path / "k"
    f.write_text("file-key\n")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENWAY_KEY_FILE", str(f))
    assert llm.cloud_key() == "file-key"


def test_hosted_model_gets_the_question_and_a_strict_schema_and_no_location(srv, monkeypatch):
    slots = '{"intent":"parking","need":"accessible_parking","place_type":null,"region":null,"place_name":"zoo","date_words":null}'
    sent = hosted(monkeypatch, lambda body: slots if "slots" in body["messages"][0]["content"] else "{}")
    body = {**ASK, "context": {"today": "2026-11-20", "location": [39.12345, -84.54321]}}
    ev = events(requests.post(srv + "/api/ask", json=body, timeout=30))
    assert ev[-1]["type"] == "done" and not any(e["type"] == "error" for e in ev)
    assert sent and sent[0]["url"].endswith("/chat/completions")
    first = sent[0]["json"]
    assert first["model"] == llm.CLOUD_MODEL and "temperature" not in first
    schema = first["response_format"]["json_schema"]
    assert schema["strict"] is True and schema["schema"]["additionalProperties"] is False
    assert sent[0]["headers"]["Authorization"] == "Bearer test-key"
    everything = json.dumps([s["json"] for s in sent])
    assert "39.12345" not in everything and "-84.54321" not in everything
    assert "test-key" not in json.dumps(ev)


def test_strict_schema_closes_objects_and_drops_length_limits():
    s = llm._strict(llm.COMPOSE_SCHEMA)
    assert s["additionalProperties"] is False
    assert s["properties"]["sentences"]["items"]["additionalProperties"] is False
    assert (
        "maxItems" not in s["properties"]["sentences"]
        and "maxItems" in llm.COMPOSE_SCHEMA["properties"]["sentences"]
    )


def test_strict_schema_writes_a_choice_that_may_be_null_as_any_of():
    need = llm._strict(llm.SLOT_SCHEMA)["properties"]["need"]
    assert "type" not in need and "enum" not in need
    assert need["anyOf"][1] == {"type": "null"}
    assert need["anyOf"][0]["type"] == "string" and None not in need["anyOf"][0]["enum"]
    assert llm.SLOT_SCHEMA["properties"]["need"]["type"] == ["string", "null"]  # the local form is unchanged


def test_hosted_model_failure_still_gives_a_rules_answer(srv, monkeypatch):
    hosted(monkeypatch, lambda body: "not json")
    ev = events(requests.post(srv + "/api/ask", json=ASK, timeout=30))
    assert ev[-1]["type"] == "done" and ev[0]["type"] == "text"


def test_over_the_visitor_limit_the_answer_comes_from_guided_mode(srv, monkeypatch):
    sent = hosted(monkeypatch, lambda body: "{}")
    monkeypatch.setattr(server, "RATE_PER_HOUR", 2)
    for _ in range(2):
        requests.post(srv + "/api/ask", json=ASK, timeout=30)
    used = len(sent)
    ev = events(requests.post(srv + "/api/ask", json=ASK, timeout=30))
    assert ev[0] == {"type": "note", "message": server.HOSTED_NOTE}
    assert ev[-1]["type"] == "done" and len(sent) == used  # no model call for the third question


def test_limits_count_per_visitor_per_hour_and_for_everyone_per_day(monkeypatch):
    monkeypatch.setattr(server, "_rate", {"day": "", "total": 0, "seen": {}})
    monkeypatch.setattr(server, "RATE_PER_HOUR", 2)
    monkeypatch.setattr(server, "RATE_PER_DAY", 3)
    t = 1_800_000_000.0
    assert (
        server.allow_model("a", t) and server.allow_model("a", t + 1) and not server.allow_model("a", t + 2)
    )
    assert server.allow_model("b", t + 3)  # another visitor is not affected
    assert server.allow_model("a", t + 3601) is False  # the hour passed, but the day's total (3) is used up
    assert server.allow_model("a", t + 86400 * 2)  # a new day


def test_only_named_sites_may_call_the_api(srv, monkeypatch):
    monkeypatch.setattr(server, "ALLOW_ORIGINS", {"https://pages.example"})
    ok = requests.options(
        srv + "/api/ask",
        headers={"Origin": "https://pages.example", "Access-Control-Request-Method": "POST"},
        timeout=10,
    )
    assert ok.status_code == 204 and ok.headers["Access-Control-Allow-Origin"] == "https://pages.example"
    assert "POST" in ok.headers["Access-Control-Allow-Methods"]
    r = requests.post(
        srv + "/api/ask",
        json={**ASK, "mode": "rules"},
        headers={"Origin": "https://pages.example"},
        timeout=30,
    )
    assert r.headers["Access-Control-Allow-Origin"] == "https://pages.example"
    other = requests.get(srv + "/api/health", headers={"Origin": "https://other.example"}, timeout=10)
    assert "Access-Control-Allow-Origin" not in other.headers


def test_page_can_point_at_another_server(monkeypatch, tmp_path):
    from atlas.assistant import page

    monkeypatch.delenv("OPENWAY_SERVER_BASE", raising=False)
    assert "__OPENWAY_SERVER=" not in page.app_html()
    monkeypatch.setenv("OPENWAY_SERVER_BASE", "https://backend.example/cgi-bin/openway.cgi/")
    assert 'window.__OPENWAY_SERVER="https://backend.example/cgi-bin/openway.cgi";' in page.app_html()


def _fake_turn(monkeypatch, slots, seen=None):
    """A hosted model that returns `slots` for the planning call (and fails any other call)."""
    monkeypatch.setattr(llm, "PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def chat(messages, schema=None, **kw):
        if schema is not llm.SLOT_SCHEMA:
            raise llm.requests.RequestException("not used here")
        if seen is not None:
            seen.append(messages)
        return json.dumps(slots)

    monkeypatch.setattr(llm, "chat", chat)


TALK = {
    "intent": "other",
    "need": None,
    "place_type": None,
    "region": None,
    "place_name": None,
    "date_words": None,
}


def test_a_message_that_is_not_a_lookup_gets_the_models_own_reply(monkeypatch):
    from atlas.assistant.engine import Engine

    _fake_turn(
        monkeypatch, {**TALK, "reply": "I'm Openway. I look up step-free places. What do you need today?"}
    )
    eng = Engine(planner=llm.model_planner, composer=llm.model_composer)
    for q in ("tell me about yourself", "hi"):
        a = eng.answer(q, {"today": "2026-11-26", "region": "oxford"})
        assert a.kind == "chat" and a.text.startswith("I'm Openway."), q
        assert not a.cards and not a.sources and a.confidence == "Assistant · not from the map data"
        assert a.model_use == {"plan": "model", "answer": "model"}
        assert "reply" not in a.plan and "asked" not in a.plan


def test_the_models_reply_never_replaces_a_data_answer_or_a_safety_answer(monkeypatch):
    from atlas.assistant.engine import Engine

    _fake_turn(monkeypatch, {**TALK, "reply": "Sure, everything there is ADA compliant and safe."})
    eng = Engine(planner=llm.model_planner, composer=llm.model_composer)
    ctx = {"today": "2026-11-26", "region": "oxford"}
    assert eng.answer("where is the closest accessible restroom", ctx).kind == "answer"  # the data has cards
    assert eng.answer("call an ambulance", ctx).kind == "emergency"  # decided by rules, model not asked
    a = eng.answer("tell me about yourself", ctx)  # a banned claim in the reply is removed by the verifier
    assert "ADA compliant" not in a.full_text and a.kind == "unknown"


def test_earlier_turns_reach_the_model_cut_down_and_let_it_pick_the_place(monkeypatch):
    from atlas.assistant import server
    from atlas.assistant.engine import Engine

    seen = []
    _fake_turn(
        monkeypatch,
        {**TALK, "intent": "place_details", "place_name": "Armstrong Student Center", "reply": None},
        seen,
    )
    turns = server._turns(
        [{"role": "user", "text": "x" * 900}, {"role": "system", "text": "no"}, "junk"]
        + [{"role": "assistant", "text": "ok"}] * 9
    )
    assert len(turns) == 6 and all(len(t["text"]) <= 400 for t in turns)
    eng = Engine(planner=llm.model_planner)
    hist = [
        {"role": "user", "text": "food near Armstrong Student Center"},
        {"role": "assistant", "text": "Pulley Diner."},
    ]
    a = eng.answer("does it have an elevator?", {"today": "2026-11-26", "region": "oxford"}, history=hist)
    assert [m["content"] for m in seen[0][1:]] == [
        "Q: food near Armstrong Student Center",
        "A: Pulley Diner.",
        "Q: does it have an elevator?",
    ]
    assert a.plan["place"]["name"] == "Armstrong Student Center" and a.plan["source"] == "model"


class _FakeClaude:
    """Stands in for anthropic.Anthropic: records the request and returns one text block."""

    def __init__(self, text="{}", error=None):
        self.text, self.error, self.sent = text, error, None
        self.messages = self

    def create(self, **kw):
        self.sent = kw
        if self.error:
            raise self.error
        from types import SimpleNamespace as NS

        return NS(content=[NS(type="text", text=self.text)], usage=NS(input_tokens=11, output_tokens=7))


def test_claude_api_call_sends_system_turns_and_a_strict_schema(monkeypatch):
    pytest.importorskip("anthropic")  # only installed where the hosted model is used
    fake = _FakeClaude('{"ok": true}')
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    monkeypatch.setattr(llm, "CLOUD_MODEL", "claude-haiku-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_claude", lambda key, timeout: fake)
    assert llm.hosted() and llm.health()["model"] and llm.health()["hosted"]
    before = llm.STATS["tokens_in"]
    out = llm.chat(
        [
            {"role": "system", "content": "RULES"},
            {"role": "assistant", "content": "A: left over from a cut"},
            {"role": "user", "content": "Q: one"},
            {"role": "assistant", "content": "A: two"},
            {"role": "user", "content": "Q: three"},
        ],
        llm.SLOT_SCHEMA,
    )
    assert out == '{"ok": true}' and llm.STATS["tokens_in"] == before + 11
    sent = fake.sent
    assert sent["model"] == "claude-haiku-5-5" and sent["system"] == "RULES"
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user"]  # starts with the person
    assert sent["output_config"]["effort"] == "low"
    fmt = sent["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["additionalProperties"] is False
    assert "temperature" not in sent and "thinking" not in sent


def test_claude_api_failure_is_a_plain_fallback_and_the_key_file_is_read(monkeypatch, tmp_path):
    anthropic = pytest.importorskip("anthropic")
    import httpx2 as httpx

    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    key = tmp_path / "anthropic.key"
    key.write_text("file-key\n")
    monkeypatch.setenv("OPENWAY_KEY_FILE", str(key))
    assert llm.cloud_key() == "file-key"
    monkeypatch.setattr(llm, "_claude", lambda key, timeout: _FakeClaude(error=err))
    with pytest.raises(llm.requests.RequestException):
        llm.chat([{"role": "user", "content": "Q: hi"}], llm.SLOT_SCHEMA)
    from atlas.assistant.engine import Engine

    a = Engine(planner=llm.model_planner, composer=llm.model_composer).answer(
        "where is the closest accessible restroom", {"today": "2026-11-26", "region": "oxford"}
    )
    assert a.kind in ("answer", "clarify") and a.model_use == {"plan": "rules", "answer": "template"}
