"""Terminal chat for development:  python -m atlas.assistant.chat_cli [--today YYYY-MM-DD] [--region oxford]

Commands:  :loc LAT LON   set a location   :plain   toggle plain language   :detail   toggle details
           :json          show the last answer as JSON   :quit
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .engine import Engine
from .schema import Context


def render(a, detail: bool = True) -> str:
    out = [a.text]
    if a.clarify:
        out += [f"  - {o['label']}" for o in a.clarify.get("options", [])]
    if detail and a.details:
        out += ["", "More detail:"] + [f"  - {s.text}" for s in a.details]
    for c in a.cards:
        out.append("")
        if c.event:
            out.append(f"[{c.name}] {c.event['title']}, {c.event['when_text']}  ({', '.join(c.event['access']) or 'no access info'})")
            continue
        extra = f", {c.distance_text} {c.direction}" if c.distance_text else ""
        out.append(f"[{c.name}] {c.rating}{extra}")
        for f in c.facts:
            out.append(f"   - {f.label}: {f.value}" + (f" ({f.detail})" if f.detail else "") + f"  [{f.source or 'no source'} {f.date}]")
    if a.unknown:
        out += ["", "Not known: " + "; ".join(a.unknown)]
    if a.call:
        out.append(f"Call {a.call['name']}: {a.call['phone']}")
    if a.as_of:
        out.append(f"(data as of {a.as_of}; verified={a.verified}, removed={a.removed})")
    return "\n".join(out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--region")
    ap.add_argument("--model", action="store_true", help="use the local model (needs Ollama)")
    ap.add_argument("question", nargs="*")
    a = ap.parse_args(argv)
    eng = Engine()
    if a.model:
        from .llm import model_composer, model_planner

        eng = Engine(planner=model_planner, composer=model_composer)
    ctx = Context(today=a.today, region=a.region)
    detail = True
    last = None

    def ask(q):
        nonlocal last
        last = eng.answer(q, ctx)
        print(render(last, detail))

    if a.question:
        ask(" ".join(a.question))
        return
    print("Openway Assistant (terminal). Ask a question, or :quit. Today is", ctx.today)
    for line in sys.stdin if not sys.stdin.isatty() else iter(lambda: input("\nyou> "), None):
        q = line.strip()
        if not q:
            continue
        if q == ":quit":
            break
        if q.startswith(":loc"):
            _, lat, lon = q.split()
            ctx.location = [float(lat), float(lon)]
            print("location set (used only to sort by distance)")
        elif q == ":plain":
            ctx.plain = not ctx.plain
            print("plain language:", ctx.plain)
        elif q == ":detail":
            detail = not detail
        elif q == ":json" and last:
            print(json.dumps(last.to_dict(), indent=1, ensure_ascii=False))
        else:
            ask(q)


if __name__ == "__main__":
    main()
