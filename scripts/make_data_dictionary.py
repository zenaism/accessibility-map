"""Generate docs/data_dictionary.md from the schema definitions (src/atlas/schema.py).

python scripts/make_data_dictionary.py
"""

from pathlib import Path

from atlas.schema import COLUMN_DOCS, OBS_V2_COLUMNS, SCHEMA_VERSION, V2_EXTRA

ROOT = Path(__file__).resolve().parents[1]
lines = [
    "# Data dictionary",
    "",
    "_Generated from `src/atlas/schema.py` by `scripts/make_data_dictionary.py`. Do not edit by hand._",
    "",
    f"## Observation table (schema {SCHEMA_VERSION})",
    "",
    "One row is one claim about one attribute of one thing, with where it came from. Rows are never overwritten: a changed value "
    "is a new row (see `snapshot_date`, `valid_from`, `valid_to`). Columns marked **new** were added in v2; the connectors still "
    "write v1 and `schema.upgrade()` adds them.",
    "",
    "| Column | Type | Meaning |",
    "|---|---|---|",
]
for c in OBS_V2_COLUMNS:
    t, d = COLUMN_DOCS[c]
    lines.append(f"| `{c}` | {t} | {'**new** ' if c in V2_EXTRA else ''}{d} |")
lines += [
    "",
    "## Dataset card (one JSON file per source and region, `data/cards/<region>/<source>.json`)",
    "",
    "| Field | Meaning |",
    "|---|---|",
    "| `id`, `source`, `region`, `title` | identify the dataset |",
    "| `publisher`, `url`, `licence`, `connector` | who publishes it, where, under which terms, how we read it |",
    "| `collected`, `entities`, `observations`, `documents`, `events` | how much we hold |",
    "| `attributes` | attribute names with counts |",
    "| `bbox`, `observed_range`, `last_retrieved`, `age_days` | where and when the data covers |",
    "| `null_rates`, `duplicates_share`, `failed_fetches`, `robots_skipped` | quality and completeness measures |",
    "| `trust` | source score 0 to 100, tier A to D and the component values (see `config/trust.yaml`) |",
    "| `known_issues` | plain-language warnings generated from the measures |",
    "",
    "## Facts table (`data/processed/<region>/<source>.facts.parquet`, from `atlas extract`)",
    "",
    "| Field | Meaning |",
    "|---|---|",
    "| `doc_id`, `url`, `place`, `section` | the document, its address, its title, the heading path the sentence sits under |",
    "| `attribute`, `value`, `detail` | what is stated (attribute from `config/attributes.yaml`; yes, limited or no) and the key words |",
    "| `evidence_quote`, `quote_verified` | the verbatim sentence, checked against the document text |",
    "| `method`, `trigger` | rules, rules+llm or llm, and the phrase that matched |",
    "| `extractor`, `model`, `prompt_version` | version of the rules, the local model and the prompt version, so a later run adds rows instead of overwriting |",
    "| `confidence`, `extracted_at` | 0 to 1 (rules 0.5, rules confirmed by the model 0.8, model only 0.55) and when |",
    "",
    "## History archive (`data/history/<kind>/<region>/<YYYY-MM>.jsonl`, from `atlas archive`)",
    "",
    "One JSON line per snapshot with `fetched_at` and the raw answer: `weather` (current conditions), `alerts` (active weather alerts), `transit` (GTFS-Realtime service alerts).",
    "",
    "## Candidate source table (`data/candidates/source_candidates.csv`)",
    "",
    "| Field | Meaning |",
    "|---|---|",
    "| `candidate_id` | short hash of the URL |",
    "| `url`, `title`, `publisher`, `region` | the candidate source |",
    "| `route` | how it was found: A catalogs, B government site, C place-driven, D search |",
    "| `authority_kind` | official_inventory, official_site, open_dataset, venue_statement, crowd, lived_experience, unknown |",
    "| `licence`, `data_year` | stated terms and the year of the data, if known |",
    "| `state` | new, triaged, approved, quarantined, rejected, ingested, stale or retired |",
    "| `score`, `tier`, `reason` | trust score 0 to 100, tier A to D, and the components used |",
    "| `added_at`, `updated_at` | dates |",
    "",
    "## Raw-store manifest (`data/raw/manifest.jsonl`)",
    "",
    "One line per network fetch: `key` (cache file name), `url` (parameter names only, never values), `method`, `status`, `sha256`, `bytes`, `retrieved_at`.",
    "",
]
(ROOT / "docs/data_dictionary.md").write_text("\n".join(lines))
print("wrote docs/data_dictionary.md")
