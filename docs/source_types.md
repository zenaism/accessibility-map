# Source types beyond government data

Research on what else we need besides government sources, and how each kind is reached, licensed and extracted. Researched 2026-11-15.

**Confidence labels.** *Checked* = confirmed in a web search on 2026-11-15 (link given). *Unchecked* = from general knowledge or the existing repo docs; verify before relying on it. Licences change; always re-read the source's terms before redistributing.

Government data (city and state GIS, 311, ADA plans, GTFS) is covered in [`data_landscape.md`](data_landscape.md) and [`source_catalog.md`](source_catalog.md). This file is about everything else, plus first findings for the target regions. Diagrams: [`architecture.md`](architecture.md).

## 1. Why government data is not enough

| What a wheelchair user asks | Government data usually has | What is missing |
|---|---|---|
| Can I get into this restaurant or shop? | nothing | entrances, door width, restrooms: only venues and crowds know |
| Is the sidewalk usable today? | an inventory made years ago (DC's ramp condition data was captured in 2016) | current condition, obstructions, what changed |
| What is the venue like inside? | nothing | layout, elevators, seating, sensory info |
| Is the event accessible? | sometimes a calendar | access notes, ASL, quiet hours: on organizers' pages and posters |
| What do people actually experience? | complaint counts (311), biased by who reports | lived experience in words |
| Is the data right? | self-reported compliance | independent checks |

So the plan needs eight further kinds of source. They differ in effort, legality and trust, so each is tiered below.

## 2. Source types

### A. Open community geodata (structured, free, national)
| Source | What it gives | Access and licence | Status |
|---|---|---|---|
| OpenStreetMap | places with `wheelchair` tags, footways, kerbs, crossings, entrances | ODbL; Overpass or extracts | in use. Weak on access tags (1.6% of named places in our data) |
| Overture Maps places | complete POI list, categories, websites: the denominator for coverage | per-record licence by `source`; Foursquare-sourced rows are Apache 2.0 and need the Foursquare NOTICE kept; no OSM data inside. Checked: [Overture attribution](https://docs.overturemaps.org/attribution), [release notes](https://docs.overturemaps.org/blog/2025/09/24/release-notes/) | in use |
| Foursquare Open Source Places | 100M+ POIs | Apache 2.0, attribution. Checked: [OSM community note](https://community.openstreetmap.org/t/foursquare-releases-100m-poi-dataset-under-apache-2-0/121883) | not used separately; mostly via Overture |
| Wikidata (property P2846 "wheelchair accessibility") and Wikimedia Commons | accessibility flags and photos for notable places and heritage sites | CC0 (Wikidata); Commons files have per-file licences | Checked: wheelchair is one of the better-covered accessibility fields, but overall accessibility data on Wikidata is thin ([Wikimedia UK](https://wikimedia.org.uk/?p=7109)). Count not found: run a SPARQL query |
| Mapillary street imagery | street photos plus 150+ detected object classes through an API | CC BY-SA imagery; API needed for detections. Checked: [Mapillary blog](https://blog.mapillary.com/update/2024/07/08/expanding-public-street-level-imagery-access.html), [help](https://help.mapillary.com/hc/en-us/articles/360010234680-accessing-mapillary-data-through-api) | Not confirmed: a curb-ramp class. Check the class list; share-alike on derived data needs a licence review |
| Project Sidewalk | crowd-labelled curb ramps, obstacles, surface problems for several cities | CC0, open APIs and downloads. Checked: [Project Sidewalk](https://sidewalk-dc.cs.washington.edu) (DC deployment exists) | check which cities are live and recent |
| OpenSidewalks / TDEI (UW Taskar Center) | pedestrian network schema and data. Demonstration regions include **Baltimore County, Montgomery County (MD)** | free portal account to download. Licence is stated inconsistently (CC0 in one record, "other" in another). Checked: [TDEI on Data.gov](https://catalog.data.gov/dataset/its4us-demonstration-region-data-on-the-tdei), [UW news](https://www.washington.edu/news/2025/03/25/os-connect-accessmap-accessible-sidewalks/) | very relevant to Maryland. Confirm the licence with the data owner |
| Wheelmap and accessibility.cloud | 1.6M+ places with wheelchair status; aggregates about 90 partner datasets | OSM-based part is ODbL; API needs a token. Checked: [OSM wiki Wheelmap](https://wiki.openstreetmap.org/wiki/Wheelmap). accessibility.cloud's own data terms not found | strongest in Europe; check US density first |
| USGS 3DEP elevation | slope for any US place | public domain | in use for Oxford |
| Census ACS (S1810) and CDC data | disability prevalence by tract | public | next. Useful for equity (RQ1), not for place facts |

### B. Crowdsourced accessibility apps and platforms
| Source | What it gives | Access |
|---|---|---|
| AXS Map | venue ratings (1 to 5 stars for mobility, plus entrance, parking, noise, light) from mapathons and users | Checked: no public API or open dataset found ([AXS Map](https://www.axsmap.com/about-us)). Ask for a research data agreement |
| Wheel the World | verified hotel, tour and attraction access details with measurements | no data API found; public listings only; ask for a partnership |
| RollMobility, WheelMate, iAccess Life, AccessibleGO | reviews and measurements of entrances, restrooms, tables | apps; ask for exports |
| Universal Changing Table Map, Changing Places | adult changing tables | the maps are public pages; check each one's terms and whether it is still online (the earlier check found the domain down) |
| Our own visitor ratings (Supabase) | one-tap ratings from map users | ours, so no licence problem; label as crowd data |

Strategy: for every platform without an API, write one short data-request email (the repo already has a drafts file, [`outreach_emails.md`](outreach_emails.md)), and meanwhile use only what is public and allowed.

### C. Venue, tourism and institutional websites (the main source for consumer questions)
- **Venue sites:** museums, theatres, stadiums, zoos, airports, malls, hotels, restaurants. They usually have an "Accessibility" or "Plan your visit" page and sometimes a PDF guide.
- **Tourism and destination boards** (for example Enjoy Oxford, Visit Cincy, Travel Butler County): visitor guides with accessibility icons.
- **Universities and hospitals:** campus accessibility maps, parking and drop-off, clinic access. UC Health, Cincinnati Children's and campus sites are already on the list.
- **Parks and trail sites:** county and state parks, trail systems, track chair loans.
- **Nonprofits and advocacy:** independent living centers, Easterseals, adaptive sports groups, disability service providers: services, equipment lending, events.
- **Transit agency sites:** paratransit eligibility, accessible stop lists, elevator outage pages.
How: place-driven discovery (start from the OSM or Overture `website` field), crawl only accessibility-like pages, extract with quotes. This is route C in the discovery design. Terms and robots.txt apply, and facts plus a link are kept rather than whole-site mirrors.

### D. Documents, posters and images (the multimodal part)
| Kind | Examples | Why it matters | Method |
|---|---|---|---|
| Accessibility guides (PDF) | museum, zoo, stadium access sheets | detailed, often more precise than web text | PDF text and table extraction |
| ADA transition plans and barrier inventories | city and county plans | list of known barriers and planned fixes. Mostly static PDFs; some places also publish CSV or GeoJSON (for example Tempe). Checked: [FHWA transition plan and inventory map](https://highways.dot.gov/civil-rights/programs/ada/ada-transition-plan-and-inventory-map), [data.gov example](https://catalog.data.gov/dataset/3-14-ada-transition-plan-compliance-summary). Only about 22 of 83 responding Chicago-area municipalities had a plan ([MPC](https://metroplanning.org/?p=7502)) | table extraction plus an LLM for barrier type, location, priority |
| Maps and posters | trail maps, campus parking maps, event flyers | access markings live only in the picture | OCR plus a vision model; hand check |
| Floor plans and signage photos | venue layouts | interior routes, restroom locations | vision model, with a person verifying |
| Photos on Commons and Mapillary | entrances, ramps | evidence you can look at | vision model for entrance type; keep the image as evidence |
All claims keep the page or image region as evidence (see the extraction diagram in `architecture.md`).

### E. Lived experience and discussion
| Source | Use | Caveat |
|---|---|---|
| Reddit (accessibility, wheelchair, and city subreddits) | experiences, recommendations, complaints | Checked (secondary sources, unverified): free access is non-commercial, about 100 requests per minute, approval needed; Reddit asks research users not to redistribute data and to anonymize. Confirm on Reddit's own pages before use |
| Forums, blogs, travel writers (Curb Free with Cory Lee, WheelchairTravel.org), YouTube transcripts | first-hand venue and trail reports | opinion and dated; strip personal data; attribute and link |
| Facebook groups | local lived experience | needs the Meta Content Library or similar approved route, not scraping |
| Reviews on Google or Yelp | access comments | terms forbid storing; evaluation only (see decision D-08 in [`decisions.md`](decisions.md)) |
Treat as *signal with low confidence*: it can suggest a barrier to check, not settle it.

### F. Events and programs
iCal and calendar feeds, WordPress event APIs, Eventbrite and Meetup pages, library and theatre calendars, adaptive sports leagues, race events (for example wheelchair divisions). Accessibility notes are often only on the event page or flyer, so documents (D) and web (C) methods apply.

### G. News and alerts (temporary conditions)
Local news and agency alert pages for closures, elevator outages, construction, flooding and snow; GTFS-Realtime alerts; DOT 511 feeds. These are short-lived: store with a validity window so the assistant does not report old closures as current.

### H. Structured data embedded in web pages
Schema.org markup (JSON-LD) on venue sites, open Web Data Commons extracts. Checked: schema.org has `accessibilityFeature` and `accessibilityHazard`, but they were designed for digital content, and no coverage figures for venues were found ([W3C crosswalk](https://www.w3.org/community/reports/a11y-discov-vocab/CG-FINAL-crosswalk-20240906/)). Cheap to try as a by-product of the crawl; do not expect much.

### I. Research datasets and our lab's own sensor data
- **Published datasets and models:** annotated sidewalk and curb-ramp imagery (for example the RampNet work on curb-ramp detection from government metadata, [paper](https://arxiv.org/abs/2508.09415v1)); related Miami work (OmniPath, OmniAcc) from the literature review.
- **The lab's own data:** mmRAMP (radar, camera, depth, motion) and SurfaceEncoder surface classification from the wheelchair. This is ground truth no outside source has and anchors RQ2.
Use for evaluation and training, with each dataset's licence recorded.

### J. Commercial and restricted APIs (comparison, not storage)
Google Places, Yelp Fusion, Foursquare Places API, Bing and HERE. Terms generally forbid keeping the data. Use for live lookups and as an independent yardstick for how complete and correct our data is.

### K. Direct partnerships and requests
Some data will only come from asking: city engineering departments (sidewalk and ramp layers), disability services offices (campus accessibility maps), transit agencies (current GTFS, paratransit), advocacy groups. Plan for a tracked outreach list with status.

## 3. Which source types answer which question families

Question families are from [`national_data_plan.md`](national_data_plan.md) section 2. ● = main source, ○ = supporting.

| Question family | Govt GIS | A open geodata | B crowd apps | C venue sites | D documents | E lived experience | F events | G alerts |
|---|---|---|---|---|---|---|---|---|
| 1 Route and path | ● | ● | ○ | | ○ | ○ | | ○ |
| 2 Crossings | ● | ● | | | | ○ | | |
| 3 Entering a place | | ● | ● | ● | ○ | ○ | | |
| 4 Inside a place | | | ● | ● | ● | ○ | | |
| 5 Parking and drop-off | ○ | ● | ○ | ● | ● | ○ | | |
| 6 Transit | ● | ○ | | ● | ● | ○ | | ● |
| 7 Today's conditions | ● | | | ○ | | ○ | | ● |
| 8 Events and programs | | | | ● | ● | ○ | ● | |
| 9 Services and health | ○ | ○ | | ● | ● | ○ | | |
| 10 Rights and reporting | ● | | | ○ | ● | | | |
| 11 Housing and daily needs | ○ | ● | ○ | ● | | ○ | | |
| 12 Outdoors and recreation | ○ | ● | ● | ● | ● | ○ | ○ | |
| 13 Lived experience | | | ○ | | | ● | | |

Reading it: government data carries the street-level and transit rows; venue sites, documents and crowd apps carry everything about places. That is why "venue websites plus PDFs and images" is the largest new workload.

## 4. First findings for the target regions (checked 2026-11-15)

These show the automated discovery would find real, usable sources in each place. Verify each live before ingesting.

**Washington, DC** (open data portal on ArcGIS Hub)
- *ADA Curb Ramp* (DDOT/DCGIS): inventory of barriers from the 2016 ADA Transition Plan, CC BY 4.0, downloads in GeoJSON, CSV and as an ArcGIS service. Condition data dates from 2016. [catalog record](https://catalog.data.gov/dataset/ada-curb-ramp)
- *ADA Driveway*: companion dataset from the same plan. [catalog record](https://catalog.data.gov/dataset/ada-driveway)
- *Sidewalk Ramps 2010* (planimetric ramp polygons) and *Curb 2023* (planimetric curbs): geometry only, no condition. [Sidewalk Ramps 2010](https://catalog.data.gov/dataset/sidewalk-ramps-2010)
- Project Sidewalk has a DC deployment (crowd labels).

**Maryland**
- *MDOT SHA Pedestrian Facilities* ArcGIS service: sidewalk ramps (points), sidewalks (lines), driveway crossings, median treatments, bus stops, vertical elevations along state-maintained roads. Maintained by the Office of Highway Development; no licence is stated in the item info, so ask GIS@mdot.maryland.gov. [service](https://maps.roads.maryland.gov/arcgis/rest/services/OHD_ADA/PedestrianFacilities_Maryland_MDOTSHA/MapServer)
- *Maryland Sidewalk Data Collaboration* (MDOT-led, with One Maryland One Centerline): a statewide sidewalk data effort worth contacting. [presentation](https://baltometro.org/sites/default/files/bmc_documents/committee/presentations/bpag/BPAG250716_OMOC-Sidewalk-Data-Collaboration.pdf)
- *Baltimore County* publishes a pedestrian curb ramps layer with an ADA compliance attribute.
- *OpenSidewalks/TDEI* has Baltimore County and Montgomery County data (see A).
- County and city ADA self-evaluations and transition plans exist as PDFs (for example Washington County).
- Not confirmed: whether these are in the iMAP portal, and bulk download and licence terms.

**Dayton, Ohio**
- *City of Dayton ADA Self-Evaluation and Transition Plan* (July 2023) and appendices, including curb status by neighbourhood: PDF extraction target. [plan](https://daytonohio.gov/DocumentCenter/View/13774/Dayton-ADA-SETP-Public-Review-Version)
- *ODOT ADA Sidewalk Inventory* ArcGIS layer (statewide, state-maintained routes; metadata dated April 2026): query for the Dayton extent. [layer](https://tims.dot.state.oh.us/ags/rest/services/MapViewers/ADA_Sidewalk_Inventory/MapServer)
- Montgomery County GIS offers downloads and requires credit; no county sidewalk or ramp layer found.
- A city contractor inventoried curbs, sidewalks and ramps in several neighbourhoods; ask the city for the data.

Pattern: every region has (1) a state DOT layer for state routes, (2) an ADA plan PDF per city or county, (3) a patchy city layer, and (4) national and crowd layers (OSM, Overture, Mapillary, Project Sidewalk). That supports the plan's "national layers plus discovered local layers" split.

## 5. Priorities

1. **Free, national, structured, high coverage:** OSM, Overture, 3DEP, Census, Mobility Database GTFS, state DOT ADA layers (Ohio, Maryland and similar). Build these first; they work for any region.
2. **Place-driven venue sites and tourism boards:** largest value for consumer questions; needs the extraction pipeline.
3. **ADA transition plans and barrier-inventory PDFs:** unique and high value; a good first multimodal target (Dayton and DC give two test cases).
4. **Crowd open data:** Project Sidewalk, OpenSidewalks/TDEI, Mapillary (after licence review), Wheelmap (after checking US density).
5. **Lived experience:** Reddit after approval, others as low-confidence signal.
6. **Partnerships and requests:** start the emails now; replies take weeks.
7. **Commercial APIs:** evaluation only.

## 6. Open questions
- Which licence terms can we accept for the dataset the other team will use (share-alike data such as Mapillary and ODbL OSM affect redistribution)?
- Is Reddit access (and its approval time) worth it for the first release?
- Does the lab want street imagery (Mapillary) in scope, or only documents, posters and maps?
- Who sends the data-request emails (AXS Map, Wheel the World, TDEI, Maryland GIS)?
