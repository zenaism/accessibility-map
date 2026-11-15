# System architecture (diagrams)

Mermaid diagrams, so they render in Obsidian and on GitHub and stay diffable as text. Colour key used in every diagram: **green = exists today** (Cincinnati and Oxford pipeline), **blue = planned** in [`national_data_plan.md`](national_data_plan.md), **grey = external**. Reasons behind the choices are in [`decisions.md`](decisions.md).

## 1. The whole system in one picture

Read left to right: where data comes from, what we do to it, what comes out, who uses it.

```mermaid
flowchart LR
  subgraph SRC["Sources"]
    direction TB
    S1["Open geodata: OSM, Overture, elevation, Census"]
    S2["Government: city and state GIS, 311, ADA plans, transit GTFS"]
    S3["Venue and tourism websites, hospitals, universities, nonprofits"]
    S4["Documents: PDFs, posters, maps, floor plans"]
    S5["Community: crowd maps, forums, our own ratings"]
  end
  subgraph PIPE["Pipeline"]
    direction TB
    P1["1 Discover sources"]
    P2["2 Review and approve"]
    P3["3 Fetch to raw store"]
    P4["4 Extract: text, tables, OCR, vision"]
    P5["5 Normalize to entities and observations"]
    P6["6 Fuse: dedupe, conflicts, confidence"]
    P1 --> P2 --> P3 --> P4 --> P5 --> P6
  end
  subgraph OUT["Outputs"]
    direction TB
    O1["Versioned release: GeoParquet plus dataset cards"]
    O2["DuckDB knowledge base"]
    O3["Map and text pages"]
  end
  subgraph USE["Users of the data"]
    direction TB
    U1["Accessibility assistant"]
    U2["Other lab team's app"]
    U3["Researchers and papers"]
  end
  SRC --> P1
  P6 --> O1
  O1 --> O2
  O1 --> O3
  O2 --> U1
  O1 --> U2
  O1 --> U3
  O3 --> U3

  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef ext fill:#eeeeee,stroke:#777,color:#111
  class S1,S2,S4,P3,P4,P5,O2,O3 built
  class P1,P2,P6,O1,S3,S5,U1,U2 planned
  class U3 ext
```

## 2. Discovery: how new sources are found without hand-picking

Four routes feed one candidate table. Nothing reaches the release without passing review.

```mermaid
flowchart TB
  R["Region added: name, FIPS, OSM relation"]
  R --> A & B & C & D
  A["A Open-data catalogs: Data.gov, Socrata, ArcGIS Hub, Mobility Database"]
  B["B Government site crawl: .gov seeds, sitemap, link scoring"]
  C["C Place-driven: OSM and Overture POIs, website tag, accessibility pages"]
  D["D Templated search queries via a search API"]
  A & B & C & D --> CAND[("source_candidates table")]
  CAND --> T["Triage: LLM reads metadata and a short sample only"]
  T --> V{"Automated checks: inside region, geometry, sane values, licence, robots.txt"}
  V -- fail --> REJ["Rejected, remembered so not re-proposed"]
  V -- pass --> H{"Human review: accept, fix mapping, reject"}
  H -- reject --> REJ
  H -- accept --> REG["Added to source registry sources.yaml"]
  REG --> F["Fetch and ingest"]
  H -. accepted mappings become examples .-> T

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  class R,A,B,C,D,CAND,T,V,H,REG,F planned
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class REJ bad
```

## 3. Multimodal extraction: from raw file to checked claims

Every input type ends as the same thing: claims with a quote or image region, so a person can verify the original.

```mermaid
flowchart LR
  RAW[("Raw store: file plus manifest, hash, licence")] --> TYPE{"What is it?"}
  TYPE -->|HTML page| H1["Main content to markdown, split by heading"]
  TYPE -->|Text PDF| H2["Text and tables with page and bbox"]
  TYPE -->|Scanned PDF, poster, flyer| H3["OCR plus vision model for layout and meaning"]
  TYPE -->|Map, floor plan, signage photo| H4["Vision model lists access features, with confidence"]
  TYPE -->|Table or barrier inventory| H5["Table parser, one row per barrier"]
  TYPE -->|Structured API or GIS layer| H6["Field mapping from sources.yaml"]
  H1 & H2 & H3 & H4 & H5 --> CL["LLM turns chunks into typed claims against attributes.yaml"]
  CL --> Q{"Quote really appears in source text, or image region exists?"}
  Q -- no --> DROP["Claim dropped"]
  Q -- yes --> CONF["Confidence score and extraction method recorded"]
  H6 --> OBS
  CONF --> OBS[("observations table")]

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  class H1,H2,H3,H4,H5,CL,Q,CONF,TYPE planned
  class RAW,H6,OBS built
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class DROP bad
```

## 4. Data model: what the tables are and how they connect

Every fact is an observation tied to an entity and a source. We keep all observations, including ones that disagree.

```mermaid
erDiagram
  REGION ||--o{ ENTITY : contains
  ENTITY ||--o{ OBSERVATION : "has facts"
  SOURCE ||--o{ OBSERVATION : "provides"
  SOURCE ||--o{ DOCUMENT : "fetched as"
  DOCUMENT ||--o{ OBSERVATION : "evidence for"
  DATASET_CARD ||--|| SOURCE : "describes"
  ENTITY ||--o{ MATCH : "linked by"
  MATCH }o--|| OBSERVATION : "attaches"

  REGION { string region_id string osm_relation string fips }
  ENTITY { string entity_id string type string name geometry geom }
  OBSERVATION { string attribute string value string signal float confidence string method date observed_at string quote }
  SOURCE { string source_id string url string licence string connector }
  DOCUMENT { string doc_id string sha256 string media_type date fetched_at }
  DATASET_CARD { int rows string fields float coverage date freshness }
  MATCH { float score string basis string status }
```

## 5. Storage and release: what the other team receives

```mermaid
flowchart TB
  subgraph LOCAL["Working storage (not published)"]
    RAWF["raw/region/source/date: original files plus manifest.json"]
    WORK["processed/region: Parquet and GeoParquet"]
  end
  subgraph REL["Release v N (published)"]
    T1["entities.parquet"]
    T2["observations.parquet"]
    T3["documents.parquet"]
    T4["sources and dataset cards"]
    T5["data dictionary, changelog, LICENSES manifest"]
  end
  RAWF --> WORK --> REL
  REL --> K["DuckDB knowledge base plus text-chunk embeddings"]
  REL --> M["GeoJSON map files and text pages for GitHub Pages"]
  REL --> TEAM["Other lab team's app: reads files, no code from us needed"]
  REL -. later if needed .-> API["Read-only API over DuckDB"]
  K --> AST["Accessibility assistant"]
  M --> VIS["Public maps"]

  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  class RAWF,WORK,K,M,AST,VIS built
  class T1,T2,T3,T4,T5,TEAM,API planned
```

## 6. Assistant at question time

The model never answers from memory. It calls tools; the tools return records with sources; the answer is written only from those records.

```mermaid
sequenceDiagram
  actor User as Wheelchair user
  participant LLM as Assistant model
  participant Tools as Query tools
  participant DB as DuckDB
  participant Docs as Document index
  User->>LLM: "Nearest accessible restroom open now, I use a power chair"
  LLM->>Tools: locate(my location)
  Tools-->>LLM: lat, lon, region
  LLM->>Tools: find_places(restroom, near, radius, accessible stall)
  Tools->>DB: filter plus distance sort
  DB-->>Tools: ranked places with facts, quotes, dates, sources
  Tools-->>LLM: records with evidence
  opt open question or detail missing
    LLM->>Docs: search(entity, "door width")
    Docs-->>LLM: passages with source and date
  end
  LLM-->>User: Answer with source, date, and "unknown" where data is missing
```

## 7. Adding a new region (what "region in a box" means)

One command per place; the same steps for Maryland, DC, Dayton and later every state.

```mermaid
sequenceDiagram
  actor You
  participant CLI as atlas region add
  participant Geo as Census TIGER and OSM
  participant Disc as Discovery
  participant Rev as Review queue
  participant Pipe as Fetch, extract, fuse
  participant Rel as Release and coverage report
  You->>CLI: add "Washington DC"
  CLI->>Geo: resolve boundary, FIPS, OSM relation
  Geo-->>CLI: pinned region entry
  CLI->>Disc: run routes A to D
  Disc-->>Rev: candidate sources with draft mappings
  You->>Rev: accept, fix or reject each one
  Rev->>Pipe: approved sources only
  Pipe->>Rel: observations, dataset cards, coverage per attribute
  Rel-->>You: "What can the assistant answer here" report
```

## 8. Review states for a source

```mermaid
stateDiagram-v2
  [*] --> new: discovered
  new --> triaged: LLM reads metadata
  triaged --> rejected: checks fail or low relevance
  triaged --> needs_review: checks pass
  needs_review --> approved: accepted by a person
  needs_review --> rejected: rejected by a person
  approved --> ingested: fetched and extracted
  ingested --> stale: past refresh date
  stale --> ingested: re-fetched
  ingested --> retired: source gone or licence changed
  rejected --> [*]
  retired --> [*]
```
