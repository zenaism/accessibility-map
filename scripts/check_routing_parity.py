"""Compare the JavaScript router with Python on many random pairs (extra to the 20 golden pairs).

    PYTHONPATH=src python scripts/check_routing_parity.py --region oxford --n 300 --out /tmp/parity.json
    node scripts/check_routing_parity.js /tmp/parity.json

Pairs are random graph nodes (jittered a little) within 3 km of each other.
"""

import argparse
import json
import math
import random

from atlas import routing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="oxford")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    _, nodes, _, lat0 = routing.network(a.region)
    rnd = random.Random(99)
    out = []
    while len(out) < a.n:
        i, j = rnd.randrange(len(nodes)), rnd.randrange(len(nodes))
        p, q = nodes.iloc[i], nodes.iloc[j]
        if math.hypot((p.lon - q.lon) * math.cos(lat0), p.lat - q.lat) * 111320 > 3000:
            continue
        pa = [p.lat + rnd.uniform(-3e-4, 3e-4), p.lon + rnd.uniform(-3e-4, 3e-4)]
        pb = [q.lat + rnd.uniform(-3e-4, 3e-4), q.lon + rnd.uniform(-3e-4, 3e-4)]
        for prof in ("wheelchair", "blind"):
            r = routing.route(a.region, *pa, *pb, prof)
            if r:
                r = {k: v for k, v in r.items() if k not in ("line", "note")}
            out.append({"from": pa, "to": pb, "profile": prof, "result": r})
    json.dump(out, open(a.out, "w"))
    print(len(out), "cases ->", a.out)


if __name__ == "__main__":
    main()
