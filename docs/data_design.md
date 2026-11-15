# Data design: scope, categories, record shapes, pipeline and map

_Current model for Cincinnati and Oxford. Once `national_data_plan.md` is approved, its observation schema v2 replaces the record shapes below; this file then keeps scope, categories, pipeline and map._

## Goal and scope

We will build one evidence layer covering access, places, trails, events and lived experience in Cincinnati and Oxford, OH. Two products sit on top of it: a question-answering assistant for wheelchair users, and a GeoJSON map file. Each answer must cite its source, give the date it was recorded, and say "unknown" when we have no evidence.

**Users.** Manual and power wheelchair users, scooter users, and their companions and caregivers. Secondary users are planners and researchers.

**Geography.** The full City of Cincinnati limits (every neighborhood, not only downtown) plus a 25 km buffer for trails and day trips (Hamilton County, Northern Kentucky riverfront). The full City of Oxford limits, including Miami's main campus, plus a 15 km buffer (Hueston Woods, Miami University, Butler County). The boundaries already live in `config/regions.yaml`. We will add a `buffer_km` field there.

**What exists today.** The repo already has 12 working connectors (OSM, CAGIS ramps, sidewalks, steps and signals, 311, Metro and BCRTA GTFS, USGS slope). It has 355,568 observations in a shared observation table, `core.OBS_COLUMNS`. That table answers questions about streets and paths. It does not cover destinations (restrooms, museums, cafes), trails, events or community posts. This plan adds those four layers without breaking the existing schema.

**Out of scope for v1.** Turn-by-turn routing, live parking availability, medical advice, and any automated posting to social networks.

## Data categories and schema

We will store everything as **entities plus observations**. The existing observation table stays as it is. We will add three record types beside it: `place`, `trail` and `event`. Free text (posts, reviews, guides) becomes `document` chunks linked to entities. One fact = one observation row, so conflicting sources can sit side by side.

### Categories

| Category | Examples | Key accessibility attributes |
| --- | --- | --- |
| Restrooms | public, park, library, venue, Changing Places / adult changing table | accessible stall, grab bars, adult changing table, family/all-gender, hours, step-free route to it |
| Food and drink | cafes, restaurants, bars, breweries, ice cream | step-free entrance, door width, accessible restroom, table height, outdoor seating, accessible parking |
| Culture | museums, galleries, theaters, libraries, historic sites | step-free entry, elevators, loaner wheelchairs, sensory hours, ASL/captions, accessible seating, companion tickets |
| Outdoors | trails, parks, gardens, overlooks, nature centers, fishing piers | surface, width, grade, length, loop/out-and-back, accessible parking, restroom at trailhead, benches, all-terrain chair loans |
| Sports and recreation | adaptive sports leagues, pools, gyms, stadiums, bowling | adaptive equipment, lift into pool, wheelchair seating, adaptive programs |
| Shopping and services | groceries, pharmacies, malls, banks, post offices | step-free entry, motorized carts, accessible checkout |
| Health and support | Independent living centers, wheelchair repair, DME suppliers, paratransit, disability offices | services, eligibility, phone, hours |
| Transport | bus stops, streetcar, Amtrak, CVG airport, accessible parking, taxi/rideshare WAV | level boarding, ramp/lift, accessible stall count |
| Lodging | hotels, Miami University visitor lodging | roll-in shower, accessible room count |
| Events | accessibility events, adaptive sports, sensory-friendly shows, festivals, support groups | date/time, venue, accessibility features listed, cost, registration link |
| Street network | sidewalks, curb ramps, crossings, steps, slope, 311 issues | already collected |
| Lived experience | Facebook, Reddit, reviews, blogs | free-text claims, author type, date |

### Record shapes

All records are stored as Parquet in `data/processed/<region>/`, with GeoParquet for geometry. A JSON Lines copy of documents feeds the index.

**place** (one row per real-world place, after deduplication)

| Field | Type | Notes |
| --- | --- | --- |
| `place_id` | string | `atlas:place:<hash>`; stable across rebuilds |
| `name`, `category`, `subcategory` | string | category from the table above |
| `lat`, `lon`, `address`, `region` | float / string | WGS84 |
| `phone`, `website`, `hours` | string | hours as OSM `opening_hours` syntax |
| `source_ids` | list\[string\] | e.g. `osm:node/123`, `overture:…`, `yelp:…` |
| `access_summary` | struct | rolled-up value per attribute: `yes / limited / no / unknown` + evidence count + latest date |

**trail**: `trail_id`, name, managing agency, geometry (LineString), length\_km, surface, typical/max grade %, min width, loop flag, trailhead place\_ids, wheelchair rating (`paved accessible / firm compact / rough / not accessible / unknown`), source\_ids.

**event**: `event_id`, title, description, start/end (ISO 8601 with tz), recurrence, venue place\_id (or lat/lon + address), organizer, cost, url, `accessibility_features` (list), `is_disability_focused` (bool), source, retrieved\_at, expires\_at.

**document**: `doc_id`, text (chunk of 300–500 tokens), source, url, author\_type (`official / business / community / reviewer`), posted\_at, linked entity ids, region, language.

**observation**: unchanged `OBS_COLUMNS`. New attribute names are added to a controlled vocabulary file, `config/attributes.yaml`, so `restroom_accessible` never also appears as `accessible_bathroom`.


## Pipeline

Every source runs through the same seven steps, built on the existing cached `core.fetch`. The raw bytes stay in `data/raw/`, so every table can be rebuilt offline.

1. **Collect.** One connector per source type: `api`, `ical`, `wp_events`, `html_crawl`, `pdf`, `image_poster`, `manual_csv`. Each source has an entry in `config/sources.yaml` with its URL, region, license, refresh interval and robots.txt check. Crawls send at most 1 request per second, identify the project in the User-Agent, and stay inside the listed paths.
2. **Extract.** Structured feeds map straight to fields. HTML, PDF and posters go through an LLM extraction step with a JSON schema per record type. The model must quote the sentence each value came from (`evidence_quote`), so a reviewer can check it. Pages are split into `document` chunks at the same time.
3. **Normalize.** Attribute names go to the controlled vocabulary. Values go to `yes / limited / no / unknown` plus the raw text. Hours become `opening_hours` syntax, and dates become ISO 8601 in America/New\_York.
4. **Geocode.** Use coordinates the source gives first. Then try an address lookup against Overture/OSM. Then use the US Census geocoder. Store `geocode_method` and drop anything that lands outside the region buffer.
5. **Resolve entities.** Match records to one `place` when names are similar (token-set ratio of 85 or more) and they sit within 75 m, or when phone or website match. Uncertain pairs go to a review CSV instead of being merged.
6. **Score.** Each observation gets a weight from source type (official or on-site 1.0, venue page 0.9, OSM 0.8, Google/Yelp 0.7, community post 0.5) times a freshness factor (halves every 3 years). The place's `access_summary` takes the highest-weighted value and flags `conflict = true` when strong sources disagree.
7. **Publish.** Write Parquet tables, the GeoJSON map files, and the document index. Then run validation: schema checks, no coordinates outside the buffer, no event that has already ended, and a sample of 50 records per release checked by a person.

**Privacy and ethics.** Community text is stored without names, handles or profile links. Quotes are shortened to the access claim. Facebook and Reddit collection waits for IRB review (or a written exemption). Takedown requests are honored within 7 days.

## Map deliverable

The professor gets one GeoJSON FeatureCollection per region, `data/map/<region>_atlas.geojson`, for now; a web viewer can come later. GeoJSON opens directly in QGIS, geojson.io, Google My Maps and ArcGIS. Coordinates are WGS84 `[lon, lat]` (RFC 7946). Trails are LineStrings and everything else is a Point. Street-level layers (14,970 ramps, 220,792 sidewalk polygons) go in a separate `<region>_street.geojson` so the main file stays under about 20 MB.

```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [-84.5373, 39.1097]},
  "properties": {
    "id": "atlas:place:9f2c1a",
    "name": "Cincinnati Museum Center",
    "layer": "culture",
    "subcategory": "museum",
    "address": "1301 Western Ave, Cincinnati, OH 45203",
    "region": "cincinnati",
    "access": {
      "entrance_step_free": "yes",
      "restroom_accessible": "yes",
      "adult_changing_table": "unknown",
      "accessible_parking": "yes",
      "wheelchair_loan": "yes"
    },
    "access_rating": "accessible",
    "conflict": false,
    "last_verified": "2026-11-20",
    "sources": [
      {"name": "venue_access_page", "url": "https://www.cincymuseum.org/accessibility"},
      {"name": "osm", "url": "https://www.openstreetmap.org/way/..."}
    ],
    "website": "https://www.cincymuseum.org"
  }
}
```

(The values above show the format only. They are not collected data.)

**Layers:** `restroom`, `food_drink`, `culture`, `outdoors`, `trail`, `sports_rec`, `shopping_services`, `health_support`, `transport`, `lodging`, `event` (current and upcoming only, with `start` and `end`).

**access\_rating** has four values: `accessible` (step-free entry and accessible restroom are both confirmed), `partial`, `not_accessible` and `unknown`. Rating rules live in `signals.py` next to the existing ones, with tests.

We also export a flat CSV of the same features for people who prefer a spreadsheet.

