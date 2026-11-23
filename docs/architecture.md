# System architecture (diagrams)

Mermaid diagrams, so they render in Obsidian and on GitHub and stay diffable as text. Colour key used in every diagram: **green = exists today** (Cincinnati and Oxford pipeline), **blue = planned** in [`national_data_plan.md`](national_data_plan.md), **grey = external**. Reasons behind the choices are in [`decisions.md`](decisions.md).

## 1. The big picture: four layers

Data flows left to right through four layers. Each layer has one job, and the layer below only trusts what the layer above passes down.

```mermaid
flowchart LR
  L1["<b>📥 1 SOURCES</b><br/>where facts live<br/><br/>🗺️ Open maps<br/>OSM · Overture · elevation<br/><br/>🏛️ Government<br/>GIS · 311 · transit · ADA plans<br/><br/>🌐 Websites<br/>venues · tourism · hospitals<br/><br/>📄 Documents<br/>PDFs · posters · maps<br/><br/>💬 People<br/>ratings · forums"]
  L2["<b>⚙️ 2 COLLECT</b><br/>find · fetch · check<br/><br/>🔎 Discover sources<br/><br/>🤖 Auto-approve by score<br/><br/>⬇️ Fetch and save raw<br/><br/>🧪 Completeness checks"]
  L3["<b>🧠 3 UNDERSTAND</b><br/>files become facts<br/><br/>📖 Read<br/>text · OCR · vision<br/><br/>🧾 Facts with<br/>quote and source<br/><br/>📍 Match to real places<br/><br/>⚖️ Fuse<br/>conflicts · confidence"]
  L4["<b>📦 4 SERVE</b><br/>who uses it<br/><br/>🗃️ Release files<br/>for the other lab team<br/><br/>🤖 Assistant<br/>answers questions<br/><br/>🗺️ Public map<br/>and text pages<br/><br/>📊 Research papers"]
  L1 ==> L2 ==> L3 ==> L4

  classDef built fill:#d4edda,stroke:#2e7d32,stroke-width:2px,color:#111
  classDef mixed fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#111
  class L1,L2,L3,L4 mixed
```

Each box is one layer: the list inside is what it holds or does. Cincinnati and Oxford already run most of layers 1 to 3 plus the map and the assistant tools; discovery, review, completeness checks, matching and fusion, and the release files are planned. See the detailed diagrams below for each part.


## 1b. One fact's journey (a concrete example)

This is what happens to a single sentence on a zoo's website, from the web page to an answer.

```mermaid
flowchart LR
  W["🌐 Zoo website<br/>'Accessibility' page"] --> F["⬇️ Fetched and saved<br/>exactly as received<br/>+ date + hash"]
  F --> R["📖 Read<br/>'Main paths are paved<br/>and wheelchair accessible'"]
  R --> Q{"Quote really<br/>on the page?"}
  Q -- no --> X["🗑️ Dropped"]
  Q -- yes --> O["🧾 Fact<br/>place: Zoo<br/>attribute: paths<br/>value: accessible<br/>confidence: medium"]
  O --> M["📍 Matched to the<br/>Zoo on the map<br/>by name and location"]
  M --> U["⚖️ Compared with<br/>OSM and other sources"]
  U --> A["🤖 Assistant:<br/>'The zoo says main paths are<br/>accessible (zoo website, 2026).<br/>Jungle Trails: unknown.'"]

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class W,F,R,Q,O,M built
  class U,A planned
  class X bad
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
  V -- pass --> H{"Trust engine: score the source"}
  H -- "Tier D" --> REJ
  H -- "Tier A or B" --> REG["Added to source registry sources.yaml"]
  REG --> F["Fetch and ingest"]
  H -. accepted mappings become examples .-> T

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  class R,A,B,C,D,CAND,T,V,H,REG,F planned
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class REJ bad
```

## 3. Multimodal extraction: from raw file to checked claims

Every input type ends as the same thing: claims with a quote or image region, so anyone, or any later check, can verify the original.

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

_Update 2026-11-20: with no funding for a hosted model, the assistant is built as a fixed pipeline (plan, run tools, compose, verify) with a rules version and a small-local-model version; see section 12 and [`assistant_build_spec.md`](assistant_build_spec.md). The diagram below shows the principle (tools first, sources on every claim), not the final design._

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
  participant Rev as Trust engine
  participant Pipe as Fetch, extract, fuse
  participant Rel as Release and coverage report
  You->>CLI: add "Washington DC"
  CLI->>Geo: resolve boundary, FIPS, OSM relation
  Geo-->>CLI: pinned region entry
  CLI->>Disc: run routes A to D
  Disc-->>Rev: candidate sources with draft mappings
  Rev->>Rev: score each source, auto-approve tiers A and B
  Rev->>Pipe: accepted sources only
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
  needs_review --> approved: score is Tier A or B
  needs_review --> rejected: score is Tier D, or Tier C is quarantined
  approved --> ingested: fetched and extracted
  ingested --> stale: past refresh date
  stale --> ingested: re-fetched
  ingested --> retired: source gone or licence changed
  rejected --> [*]
  retired --> [*]
```

## 9. Fetching everything: the crawl and its completeness gates

The goal is that nothing we might need is silently missed. Every URL we learn about gets a final status, and a source is not "done" until the gates pass.

```mermaid
flowchart TB
  SEED["Seeds: approved source URLs"] --> FR[("Frontier: every URL seen, with a status")]
  MAP["sitemap.xml and robots.txt sitemaps"] --> FR
  FEED["RSS, Atom and calendar feeds"] --> FR
  ARCH["Wayback and Common Crawl URL lists for the same domain"] --> FR
  FR --> SCOPE{"In scope? same site, allowed by robots.txt, within depth and budget"}
  SCOPE -- no --> SK["Recorded as skipped with a reason"]
  SCOPE -- yes --> FET["Fetch with retries, rate limit, ETag"]
  FET --> KIND{"What came back?"}
  KIND -->|static HTML| EXT["Save raw and extract links"]
  KIND -->|needs JavaScript or hidden content| REN["Headless browser: render, expand tabs and accordions, click load more"]
  KIND -->|PDF, image, spreadsheet| DOC["Save file and register as document"]
  KIND -->|error, login wall, soft 404, empty| FAIL["Recorded as failed with a reason"]
  REN --> EXT
  EXT --> LINKS["New links, pagination, embedded files, iframes"]
  LINKS --> FR
  FR --> DONE{"Frontier empty or budget reached?"}
  DONE -- no --> SCOPE
  DONE -- yes --> GATES["Completeness gates, see next diagram"]

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class SEED,MAP,FEED,ARCH,FR,SCOPE,REN,LINKS,DONE,GATES planned
  class FET,KIND,EXT,DOC built
  class SK,FAIL bad
```

## 10. Completeness gates: how we know we got everything

Each gate compares what we fetched with an independent measure of what exists. Anything that does not match goes to the gap queue instead of being ignored.

```mermaid
flowchart LR
  G0["Crawl finished"] --> C1 & C2 & C3 & C4 & C5 & C6
  C1["1 Status audit: every URL fetched, failed or skipped, none unknown"]
  C2["2 Sitemap coverage: share of sitemap URLs fetched"]
  C3["3 Count check: API or GIS reports total rows, compare with rows saved"]
  C4["4 Archive check: URLs in Wayback or Common Crawl that we never saw"]
  C5["5 Keyword audit: site search for wheelchair, accessible, ADA, ramp, elevator finds pages we did not fetch"]
  C6["6 Sample audit: random pages outside the crawl, LLM and person check if relevant"]
  C1 & C2 & C3 & C4 & C5 & C6 --> R{"All gates pass?"}
  R -- yes --> OK["Source marked complete, dated, coverage recorded"]
  R -- no --> GAP[("Gap queue")]
  GAP --> A1["Retry with backoff"]
  GAP --> A2["Re-fetch with headless browser"]
  GAP --> A3["Raise depth or budget"]
  GAP --> A4["Ask the owner for the data or hand-collect"]
  GAP --> A5["Mark as blocked, record why, show in report"]
  A1 & A2 & A3 --> G0
  A4 & A5 --> REP["Coverage report per source and region"]
  OK --> REP
  REP --> HUM["Gaps listed in the release notes, nothing hidden"]

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef bad fill:#fde2e2,stroke:#b91c1c,color:#111
  class G0,C1,C2,C3,C4,C5,C6,R,OK,GAP,A1,A2,A3,A4,A5,REP,HUM planned
```

## 11. The zero-budget stack: which free tool does each step

Spend compute only where it pays: cheap rules first, small local models only on pages that pass, cache everything.

```mermaid
flowchart LR
  subgraph FIND["Find"]
    F1["OSM and Overture website fields"]
    F2["Open-data catalog APIs"]
    F3["sitemaps, Wayback and Common Crawl indexes"]
  end
  subgraph GET["Fetch"]
    G1["Python requests and a polite crawler"]
    G2["Playwright headless browser for JavaScript pages"]
  end
  subgraph READ["Read"]
    R1["Rules: keywords and section headings"]
    R2["PDF parsers: PyMuPDF, pdfplumber, Docling"]
    R3["OCR: Tesseract or PaddleOCR"]
    R4["Local open model on pages that passed the rules"]
    R5["Local vision model only on relevant images"]
  end
  subgraph KEEP["Store and share"]
    K1["Local disk raw files and Parquet"]
    K2["DuckDB file"]
    K3["Zenodo, Hugging Face or GitHub releases"]
  end
  FIND --> GET --> R1
  R1 -->|not relevant| SKIP["Skipped, recorded in coverage report"]
  R1 -->|relevant| R2 & R3
  R2 & R3 --> R4
  R3 -->|image content| R5
  R4 & R5 --> HC["Automatic checks: quote, double extraction, entailment"]
  HC --> K1 --> K2 --> K3
  CACHE[("Cache by content hash: nothing processed twice")] -.-> R4
  CACHE -.-> R5

  classDef planned fill:#dbeafe,stroke:#1d4ed8,color:#111
  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  class F1,F2,F3,G2,R1,R4,R5,HC,K3,CACHE planned
  class G1,R2,R3,K1,K2 built
  classDef bad fill:#eeeeee,stroke:#777,color:#111
  class SKIP bad
```

## 12. Delivery: from build to what people use (Openway Assistant and routing)

How the pieces fit from collecting data to the screen. **Green = exists today, blue = planned** (see [`routing_in_browser_plan.md`](routing_in_browser_plan.md), [`assistant_plan.md`](assistant_plan.md) and [`assistant_build_spec.md`](assistant_build_spec.md)). First scope: **Cincinnati and Oxford**; nothing is Ohio-specific in the code, regions come from `config/regions.yaml`, so more regions can be added later.

```mermaid
flowchart TD
  subgraph BUILD["Build time (laptop, run weekly with make refresh)"]
    S["Sources<br/>OpenStreetMap, Overture, city data,<br/>venue websites, events, 311"]:::ext
    C["Collect and read<br/>connectors and crawler"]:::built
    F["Extract facts<br/>each with a quote and source"]:::built
    T["Trust engine<br/>rates every source and fact"]:::built
    KB[("Knowledge base<br/>DuckDB")]:::built
    S --> C --> F --> T --> KB
  end

  subgraph EXPORT["Exported files (static)"]
    E1["Map data and place pages<br/>GeoJSON, HTML"]:::built
    E2["Walking network<br/>with costs per profile"]:::planned
    E3["Assistant data<br/>places, facts, events"]:::planned
  end
  KB --> E1
  KB --> E2
  KB --> E3

  subgraph SITE["Static website (GitHub Pages, free)"]
    M["Map and list"]:::built
    D["Directions panel<br/>route search in the browser"]:::planned
    A["Openway Assistant<br/>guided mode, no model"]:::planned
  end
  E1 --> M
  E2 --> D
  E3 --> A
  A -. "show on map" .-> M
  A -. "route here" .-> D
  M --> D
  M --> RP["Report a problem<br/>Supabase"]:::built
  A -.-> RP

  subgraph LAB["Research stack (your laptop only)"]
    P["Pipeline: plan, run tools,<br/>compose, verify"]:::planned
    O["Small local model<br/>Ollama"]:::planned
    EV["Evaluation<br/>question bank, trap tests"]:::planned
    KB --> P
    P <--> O
    P --> EV
  end

  classDef built fill:#d4edda,stroke:#2e7d32,stroke-width:2px,color:#111
  classDef planned fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#111
  classDef ext fill:#eeeeee,stroke:#777,color:#111
```

Reading it:

- **One build, three outputs.** The knowledge base feeds the map files, the walking network and the assistant data in the same build, so they never disagree.
- **The public site needs no server and no paid model.** Routing and the assistant's guided mode run in the visitor's browser from the exported files, and questions never leave the device.
- **The research stack is separate.** The same four-step pipeline runs on the laptop with a small local model, so we can measure what a model adds over rules alone.
- **Answers lead to actions.** The assistant can show places on the map, open the Directions panel for a place, or open the report form.
- **Freshness.** The site shows the snapshot date. Events and other fast-changing data are only as fresh as the last `make refresh`; a scheduled refresh is a pending decision.

## 13. UX flows (owner's 8 changes, 2026-11-23)

Full reasoning in [`ux_brief.md`](ux_brief.md). **Green = exists today, blue = planned.**

```mermaid
flowchart TD
  M["Map, clean start<br/>search, chips, Near me"]:::built --> R1["Results on map and list"]:::built
  M --> SV["Saved places page<br/>restore link"]:::plan
  R1 --> D["Details: key answer first"]:::plan
  SV --> D
  D -->|"More details"| D2["All facts and sources"]:::plan
  D --> RT["Directions panel"]:::built
  RT -->|"Start"| NV["Navigate: live dot, direction,<br/>spoken steps, off-route alert, re-route<br/>location stays on the device"]:::plan
  M --> A["Assistant chat<br/>short answer, one card, More"]:::plan
  A -->|"Speak"| V["Voice: tap, tap, edit, send"]:::plan
  classDef built fill:#d4edda,stroke:#2e7d32,color:#111
  classDef plan fill:#e0f2fe,stroke:#0369a1,color:#111
```

