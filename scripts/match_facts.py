"""Tie a source's extracted facts to places on the map.

python scripts/match_facts.py <source> --region <r>
"""

import argparse

from atlas.extract import match

ap = argparse.ArgumentParser()
ap.add_argument("source")
ap.add_argument("--region", required=True)
a = ap.parse_args()
out = match.run(a.source, a.region)
hit = out[out.entity_id.notna()]
print(
    f"{a.source}: {len(hit)} of {len(out)} facts tied to a place ({hit.entity_id.nunique()} places); "
    f"by method: {hit.match_method.value_counts().to_dict()}"
)
for r in hit.drop_duplicates("entity_id").head(12).itertuples():
    print(f"  {r.match_method:5} {r.match_score:3.0f}  page: {r.place[:55]!r} -> map: {r.entity_name!r}")
