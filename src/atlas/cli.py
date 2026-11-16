"""atlas fetch <source|all> --region <region|all>  |  atlas report --region <region|all>"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import time
from datetime import UTC, datetime

from .core import ROOT, config, log

LEDGER = ROOT / "data/ledger/fetch_log.jsonl"


def _ledger(entry: dict) -> None:
    """Append one line per fetch attempt: the history of what was fetched, when, and whether it worked."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _run(source: str, region: str) -> None:
    spec = config("sources")[source]
    if region not in spec["regions"]:
        return
    start, t0 = datetime.now(UTC).isoformat(timespec="seconds"), time.time()
    entry = {
        "source": source,
        "region": region,
        "type": spec["type"],
        "url": spec.get("url", ""),
        "started": start,
    }
    try:
        importlib.import_module(f"atlas.connectors.{spec['type']}").run(source, spec, region)
        entry.update(status="ok", seconds=round(time.time() - t0, 1))
    except Exception as exc:
        entry.update(
            status="error", error=f"{type(exc).__name__}: {exc}"[:300], seconds=round(time.time() - t0, 1)
        )
        _ledger(entry)
        raise
    _ledger(entry)


def main() -> None:
    ap = argparse.ArgumentParser(prog="atlas")
    ap.add_argument(
        "command",
        choices=[
            "fetch",
            "report",
            "sources",
            "dem",
            "equity",
            "inventory",
            "map",
            "cards",
            "candidates",
            "region",
            "extract",
            "discover",
            "archive",
            "agree",
        ],
    )
    ap.add_argument("source", nargs="?", default="all")
    ap.add_argument("--region", default="all")
    ap.add_argument("rest", nargs="*", help="for `region`: search <query> | add <key> <name> --relation ID")
    ap.add_argument("--relation", type=int)
    ap.add_argument(
        "--llm", action="store_true", help="for `extract`: let the local model confirm and extend the rules"
    )
    ap.add_argument("--buffer-km", type=float, default=15)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sources = config("sources")
    regions = list(config("regions")) if a.region == "all" else [a.region]
    if a.command == "sources":
        for k, s in sources.items():
            print(f"{k:24} {s['type']:9} {','.join(s['regions'])}")
        return
    if a.command == "map":
        from .export_map import write as write_map

        for f in write_map():
            print(f)
        return
    if a.command == "inventory":
        from .inventory import write

        print(write())
        return
    if a.command == "agree":
        from . import fusion

        for r in regions:
            if r in fusion.PAIRS:
                print(f"[{r}]", json.dumps(fusion.agreement(r), indent=2))
        return
    if a.command == "archive":
        from . import history

        kinds = [a.source] if a.source in history.KINDS else list(history.KINDS)
        for r in regions:
            for k in kinds:
                try:
                    out = history.KINDS[k](r)
                    print(f"[{r}] {k}: archived", len(out) if isinstance(out, list) else "1 record")
                except Exception as exc:
                    print(f"[{r}] {k}: failed ({type(exc).__name__}: {exc})")
        return
    if a.command == "discover":
        from . import discovery

        for r in regions:
            new = discovery.discover(r)
            print(f"[{r}] {len(new)} new candidate sources")
            for c in sorted(new, key=lambda c: -float(c["score"] or 0))[:15]:
                print(f"  {c['tier']} {float(c['score']):5.1f}  {c['title'][:60]:<60} {c['publisher'][:30]}")
        return
    if a.command == "extract":
        from .extract import pipeline

        for r in regions:
            if (pipeline.docs_file(a.source, r)).exists():
                f = pipeline.run(a.source, r, a.llm)
                print(f"[{r}] {a.source}: {len(f)} facts", dict(f.method.value_counts()) if len(f) else "")
        return
    if a.command == "region":
        from . import regions as reg

        if a.source == "search":
            for c in reg.search(" ".join(a.rest)):
                info = reg.describe(c["osm_relation"])
                print(
                    f"{c['osm_relation']:>9}  {info['area_km2']:>8} km2  {c['category']:<28} {c['name'][:70]}"
                )
        elif a.source == "add" and len(a.rest) >= 2 and a.relation:
            print(reg.add(a.rest[0], " ".join(a.rest[1:]), a.relation, a.buffer_km))
        else:
            print(
                'usage: region search "<place>"  |  region add <key> "<name>" --relation ID [--buffer-km N]'
            )
        return
    if a.command == "cards":
        from .cards import write as write_cards

        print(write_cards())
        return
    if a.command == "candidates":
        from . import candidates

        df = candidates.rate(candidates.seed())
        candidates.save(df)
        print(df[["candidate_id", "region", "state", "tier", "score", "title"]].to_string(index=False))
        return
    if a.command == "equity":
        from .analysis.equity import run

        print(run())
        return
    if a.command == "dem":
        from .dem import download

        for r in regions:
            download(r)
        return
    if a.command == "report":
        from .report import write

        for r in regions:
            print(write(r))
        return
    # `all` = every source that needs no credentials; failures are logged, not fatal
    todo = [s for s, v in sources.items() if not v.get("credentials")] if a.source == "all" else [a.source]
    for r in regions:
        for s in todo:
            try:
                _run(s, r)
            except Exception:
                log.exception("[%s] %s failed", r, s)
    # keep the source list current: every fetch refreshes the source inventory and the dataset cards
    try:
        from .inventory import write as write_inventory

        write_inventory()
        from .cards import write as write_cards

        write_cards()
    except Exception:
        log.exception("could not refresh the source inventory")


if __name__ == "__main__":
    main()
