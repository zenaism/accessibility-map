"""Every fetch attempt, good or bad, leaves one line in the fetch ledger."""

import contextlib
import json
import types

from atlas import cli


def _fake(ok: bool):
    def run(source, spec, region):
        if not ok:
            raise RuntimeError("boom")

    return types.SimpleNamespace(run=run)


def test_ledger_records_success_and_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LEDGER", tmp_path / "ledger" / "fetch_log.jsonl")
    monkeypatch.setattr(cli, "config", lambda name: {"s": {"type": "t", "regions": ["r"], "url": "http://x"}})
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: _fake(True))
    cli._run("s", "r")
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: _fake(False))
    with contextlib.suppress(RuntimeError):
        cli._run("s", "r")
    rows = [json.loads(x) for x in cli.LEDGER.read_text().splitlines()]
    assert [r["status"] for r in rows] == ["ok", "error"]
    assert rows[1]["error"].startswith("RuntimeError")
    assert rows[0]["url"] == "http://x"
