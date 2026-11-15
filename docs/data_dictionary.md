# Data dictionary

_Generated from `src/atlas/schema.py` by `scripts/make_data_dictionary.py`. Do not edit by hand._

## Observation table (schema 2.0)

One row is one claim about one attribute of one thing, with where it came from. Rows are never overwritten: a changed value is a new row (see `snapshot_date`, `valid_from`, `valid_to`). Columns marked **new** were added in v2; the connectors still write v1 and `schema.upgrade()` adds them.

| Column | Type | Meaning |
|---|---|---|
| `entity_id` | string | Stable id of the thing described: `<source>:<native id>` |
| `entity_type` | string | poi, path_segment, crossing, kerb, curb_ramp, barrier, entrance, transit_stop, sidewalk_polygon, reported_issue or text |
| `name` | string | Name of the entity, if it has one |
| `category` | string | Source category of the entity (OSM tag, Overture category, and so on) |
| `attribute` | string | What is being stated (a name from config/attributes.yaml or a street-layer attribute) |
| `value` | string | The stated value (yes, limited, no, unknown, or a measurement) |
| `signal` | string | Meaning for a wheelchair user: supports, limited, barrier or unknown |
| `source` | string | Source id from config/sources.yaml |
| `source_ref` | string | URL or reference of the exact record |
| `observed_at` | date | When the source says the fact was recorded; may be empty |
| `retrieved_at` | timestamp | When we fetched it (UTC) |
| `license` | string | Licence or terms the data came with; decides what we may redistribute |
| `region` | string | Region id from config/regions.yaml |
| `lat` | float | Latitude, WGS84, of a representative point |
| `lon` | float | Longitude, WGS84, of a representative point |
| `schema_version` | string | **new** Schema version this row follows |
| `source_id` | string | **new** Same as source; kept as its own column so joins to the sources and dataset-card tables are explicit |
| `snapshot_date` | date | **new** Date of the fetch this row came from (history: a changed value is a new row, never an overwrite) |
| `valid_from` | date | **new** When the fact starts to hold: observed_at if known, else the snapshot date |
| `valid_to` | date | **new** When it stopped holding; empty while it is the latest value. Expiring facts (events, closures) set it |
| `confidence` | float | **new** 0 to 1: source score x extraction reliability x freshness x corroboration - conflicts (trust.py). Empty if not rated yet |
| `method` | string | **new** How the value was obtained: structured, computed, extracted, manual or crowd |
| `evidence` | string | **new** Where to check it: the record URL, or a verbatim quote with page or image region for text |

## Dataset card (one JSON file per source and region, `data/cards/<region>/<source>.json`)

| Field | Meaning |
|---|---|
| `id`, `source`, `region`, `title` | identify the dataset |
| `publisher`, `url`, `licence`, `connector` | who publishes it, where, under which terms, how we read it |
| `collected`, `entities`, `observations`, `documents`, `events` | how much we hold |
| `attributes` | attribute names with counts |
| `bbox`, `observed_range`, `last_retrieved`, `age_days` | where and when the data covers |
| `null_rates`, `duplicates_share`, `failed_fetches`, `robots_skipped` | quality and completeness measures |
| `trust` | source score 0 to 100, tier A to D and the component values (see `config/trust.yaml`) |
| `known_issues` | plain-language warnings generated from the measures |

## Candidate source table (`data/candidates/source_candidates.csv`)

| Field | Meaning |
|---|---|
| `candidate_id` | short hash of the URL |
| `url`, `title`, `publisher`, `region` | the candidate source |
| `route` | how it was found: A catalogs, B government site, C place-driven, D search |
| `authority_kind` | official_inventory, official_site, open_dataset, venue_statement, crowd, lived_experience, unknown |
| `licence`, `data_year` | stated terms and the year of the data, if known |
| `state` | new, triaged, approved, quarantined, rejected, ingested, stale or retired |
| `score`, `tier`, `reason` | trust score 0 to 100, tier A to D, and the components used |
| `added_at`, `updated_at` | dates |

## Raw-store manifest (`data/raw/manifest.jsonl`)

One line per network fetch: `key` (cache file name), `url` (parameter names only, never values), `method`, `status`, `sha256`, `bytes`, `retrieved_at`.
