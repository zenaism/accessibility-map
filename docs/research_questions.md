# Research Questions: Ohio Access Atlas

Nov 7, 2026 · @Mariam Zenaishvili

## What this project is

We are building one map of everything a wheelchair user needs to know in Cincinnati and Oxford, Ohio. It combines city records, OpenStreetMap, 311 complaints, bus data and slope from laser height maps. Later, a small language model will answer questions from this map.

Our advantage is that the lab also has data recorded *from a wheelchair*: mmRAMP (radar, camera, depth and motion sensor) and SurfaceEncoder (surface type from vibration, accepted at ECML PKDD 2026). Few groups have both map data and chair data. Every question below uses that combination.

**What we already have (Nov 2026):**

| Region | Main data | Size |
| --- | --- | --- |
| Cincinnati | City curb ramps (CAGIS) | 14,970 ramps |
| Cincinnati | City sidewalk polygons | 220,792 |
| Cincinnati | 311 accessibility reports, 2004 to 2026 | 24,639 |
| Cincinnati | OSM places, paths, crossings | 41,959 |
| Cincinnati | Metro bus stops | 2,320 |
| Oxford | OSM places, paths, crossings | 6,315 |
| Oxford | Slope per path (USGS 1 m height map) | 3,872 segments |

First finding: only about 4% of the city's curb ramps appear as kerbs in OSM. Open maps miss most of what wheelchair users need.

## RQ1: Is accessibility fair across neighbourhoods?

**In simple words:** Do some Cincinnati neighbourhoods have fewer curb ramps, and does the city fix their broken sidewalks more slowly?

**Why it matters:** A broken sidewalk can trap a wheelchair user at home. If poorer, Black, or more disabled neighbourhoods wait longer for repairs, that is a measurable injustice a city can act on.

**How to answer it:**

1. Split the city into Census tracts (small areas of about 4,000 people).
2. For each tract, count curb ramps per km of street (CAGIS) and 311 sidewalk reports per 1,000 residents.
3. From 311, compute **days to close** each hazardous-sidewalk request (close date minus open date).
4. Join each tract with Census data: income, race, share of people with an ambulatory disability (ACS table S1810), and its 1930s redlining grade (HOLC map).
5. Fit a regression: does closing time or ramp density depend on these factors, after controlling for street length and request type?
6. Check reporting bias: richer areas may report more, not have more problems. Compare 311 counts with sidewalk condition where we can measure it.

**Data:** 311 (have), curb ramps (have), Census ACS (free API), HOLC map (Mapping Inequality project).

**What a result looks like:** "Hazardous sidewalk reports in redlined tracts take X days longer to close." One clear number plus a map.

**Effort and venue:** About 2 to 4 weeks. ASSETS (April 2027), CSCW, or FAccT.

**Status, first pass (108 tracts, 18,007 repair requests):**

| Question | Result |
| --- | --- |
| Does the city close requests more slowly in some areas? | No. Hazard ratios for income, % Black, % disability and slope are all 0.98 to 1.00, not significant. |
| Do some areas report more? | Yes. +10% hazardous-sidewalk reports per resident per $10k median income; −8% per 10 points more Black residents (controlling for sidewalk area). |
| Do some areas have fewer curb ramps? | Hilly tracts: −6% ramps per road km per 1% slope. More disabled residents: −12% per 10 points, but only marginal (p = 0.09). |

**Change of plan:** Cincinnati is not in the Mapping Inequality redlining dataset (13 Ohio cities, none of them Cincinnati), so redlining is dropped for now. Disability is overall disability, not ambulatory, until we have a Census API key.

**Update: reporting bias and spatial checks.**

| Check | Result |
| --- | --- |
| Do some areas report an open problem faster? (repeat-report method, Liu et al. 2023; 954 repeats on 12,458 problems) | No. Income 0.97 (0.94–1.00), % Black 0.98 (0.93–1.03), disability and slope also near 1. |
| Problems per resident after correcting for reporting | Income gap remains and grows: +14% per $10k (1.14, 1.09–1.20). Race gap shrinks: 0.95 (0.89–1.01). |
| Do residuals cluster in space? | Yes for reports and ramps (Moran's I 0.32–0.40, p = 0.001); weak for response time (0.09, p = 0.06). |
| Do results hold with neighbourhood-clustered errors? | Yes: income, race and slope for reports; slope for ramps. |

**What this changes:** the income gap is not just richer people complaining more. Richer tracts seem to have more reported hazards per resident. Possible reasons: older sidewalks under mature trees (root heave), more foot traffic, or a lower threshold for calling a crack a hazard. The method has limited power (wide intervals for disability).

**Next:** a spatial error model; check tree canopy and sidewalk age as explanations; test each request type separately.

## RQ2: Which map source can a wheelchair user trust?

**In simple words:** When OSM, the city and the height map disagree about a sidewalk, who is right? We let the wheelchair itself decide by riding it.

**Why it matters:** Today nobody knows how accurate each source is. A map is only useful if we know how much to trust it. Manual audits are slow and expensive, but a chair with sensors measures as it rolls.

**How to answer it:**

1. Pick about 150 to 300 segments where sources disagree (city says ramp, OSM says nothing; DEM says 7%, OSM says 3%), plus random ones as a control.
2. Ride them with the mmRAMP / SurfaceEncoder setup.
3. From the chair's sensors, measure:
   - running slope and **cross slope** from the IMU tilt (the height map cannot measure cross slope),
   - surface roughness and type from vibration (SurfaceEncoder),
   - curb lips and ramps from radar and depth.
4. Check a subset by hand (tape measure, digital level) so the chair itself is validated.
5. For each source and each attribute, compute accuracy against the chair (for example: city ramp records are right 95% of the time, OSM surface 80%).

**Data:** the atlas (have), lab sensor rig (have), new rides (to collect).

**What a result looks like:** a table of "how much to trust each source for each attribute", the first of its kind if the literature review confirms it.

**Effort and venue:** About 2 to 3 months including rides. IMWUT/UbiComp or ASSETS.

## RQ3: How sure is the map, and where should we measure next?

**In simple words:** Instead of saying "this sidewalk is accessible: yes or no", the map says "85% likely passable for you". Then it tells us which sidewalks to check next to make the map better fastest.

**Why it matters:** Most segments have missing or conflicting data. A yes/no map hides that and can send someone into a barrier. Cities also have small inspection budgets and need to know where to spend them.

**How to answer it:**

1. Use the trust scores from RQ2 to combine sources into one probability per segment and attribute (a method called truth discovery, or Dawid-Skene).
2. Turn that into "probability passable" for a given user profile (for example manual chair, max 5% slope).
3. Compute risk-aware routes: avoid routes with a high chance of a barrier, not just long ones.
4. Rank unmeasured segments by how much one more ride would reduce uncertainty on frequently used routes (value of information).
5. Simulate: if the city audits the top 100 segments we suggest versus 100 random ones, how much better do routes get?

&#91;embedded content: RQ3 loop · sources, map, routes, next rides\]

Each ride improves the trust scores, which sharpens the map, which chooses the next ride.

**Data:** atlas + RQ2 rides.

**What a result looks like:** "Auditing our top 100 segments removes X% of route failures, versus Y% for random audits."

**Effort and venue:** About 2 months after RQ2. Combined with RQ2 this is the flagship paper: IMWUT, or CHI (September 2027).

## RQ4: Does the AI know when it does not know?

**In simple words:** If you ask an AI "is this cafe entrance step-free?", does it make up an answer? We build a test set to measure that, and check whether a small model that reads our map does better.

**Why it matters:** Not all mistakes are equal. Saying "accessible" when it is not can strand someone outside. Saying "not accessible" when it is only costs a detour. Current AI tests treat both mistakes the same.

**How to answer it:**

1. Generate questions from the atlas, each with the evidence that answers it ("ramp at this corner: city record #123").
2. Add **unanswerable** questions on purpose (no data exists) and **conflicting** ones (city says yes, OSM says no).
3. Have people check a sample so the answers are trustworthy.
4. Score with an asymmetric metric: a false "accessible" costs more than a false "not accessible"; "I don't know" earns partial credit when data is missing.
5. Compare: big general AI with no data, big AI that looks up our map (RAG), and a small on-device model trained on our data.

**Data:** atlas (have) + generated questions.

**What a result looks like:** "Big AI models answer 40% of unanswerable questions confidently; the grounded small model abstains correctly 85% of the time" (example numbers, to be measured).

**Effort and venue:** About 2 to 3 months. NeurIPS Datasets and Benchmarks, or ACL/EMNLP.

## Revised research questions (after the literature review)

All four questions survive, but two are sharpened and one claim is dropped. The biggest change: our own Miami group already published close work (OmniPath, OmniAcc, MyPath, Yu 2023), so we build on it instead of repeating it. Details are in the [literature review](https://claude.ai/artifact/9JwG1L5Ct3wnJDXqPA6TnY).

|  | Original | Revised | Why the change |
| --- | --- | --- | --- |
| RQ1 | Is accessibility fair across neighbourhoods? | Do accessibility-specific 311 requests in Cincinnati get slower responses in redlined, poorer or more disabled tracts, after correcting for who reports and for hilliness? | 311 bias and redlining are studied, but never for accessibility request types or disability prevalence (Liu 2023, Hamel & Holliday 2024). We now have slope to control for hills. |
| RQ2 | Which map source can a wheelchair user trust? | How accurate are OSM, city GIS, 311 and LiDAR slope when checked against wheelchair-sensed ground truth, and can a moving wheelchair measure cross slope? | OmniPath already scores slope from LiDAR with human audits. Our new part is the chair as ground truth and cross slope from the IMU, which nobody has validated. |
| RQ3 | How sure is the map; where to measure next? | Same, plus: model trust that varies by neighbourhood, missing data that is not random, and sources that copy each other. | Truth-discovery methods exist but assume independent sources and random gaps; both fail here (OSM imports, 311 silence). |
| RQ4 | Does the AI know when it does not know? | Does weighting errors by harm (false "accessible" costs more) change which models look safe, on route and slope questions with conflicting sources, and can a small grounded model beat frontier models? | MAP (Zurich, 2026) covers place facts with safety labels. Our distinct parts: numeric harm weights, conflicts, routes, small models, US data. Use OmniAcc as our baseline system. |

**Reasoning, step by step:**

1. **RQ1 stays first.** It is the most clearly novel, needs only data we have, and fits ASSETS in April 2027.
2. **RQ2 is narrowed to what only we can do.** Slope from LiDAR alone is not new (OmniPath). Riding the chair is. Cross slope from a moving IMU is unvalidated in peer-reviewed work, so it is a concrete technical contribution.
3. **RQ3 gains realistic assumptions.** Reviewers will know that classic methods assume independent sources; showing why they fail on sidewalk data, and fixing it, is itself a result.
4. **RQ4 is positioned against MAP.** Without a clear contrast, reviewers will say it was done. Harm-weighted scoring plus route questions is the clearest gap.
5. **Dropped claim:** "first self-supervised wheelchair surface model" (Watanabe 2020 came first). SurfaceEncoder's claim should be scale and cross-country transfer.

**Before writing anything:** ask the advisor how this project relates to OmniPath and OmniAcc, and whether those authors should be co-authors.

## Plan

Start RQ1 now because it needs only data we already have; start IRB and rides in parallel because they take longest. All deadlines below are estimates: confirm each on the conference site.

**Start this month:**

- [ ] Ask the advisor: target venues, scope (Oxford city only or plus campus), co-authors
- [ ] Draft the IRB application (rides with wheelchair users, interviews)
- [ ] Email SORTA: what does `wheelchair_boarding=2` mean in the Metro feed?
- [ ] Email BCRTA for a current GTFS feed; City of Oxford for sidewalk and curb ramp records
- [ ] Email Miami Student Disability Services for the campus accessibility map export
- [ ] Join Census ACS disability data and HOLC redlining map to the Cincinnati atlas (RQ1)
- [ ] Pick the first 150 segments to ride, where sources disagree (RQ2)

**Order of papers:**

1. RQ1 equity: ASSETS 2027 (deadline expected April 2027)
2. RQ2 + RQ3 flagship: IMWUT (quarterly) or CHI 2028 (expected September 2027)
3. RQ4 benchmark: NeurIPS Datasets and Benchmarks (expected May 2027) or ACL/EMNLP

**Slope data status:** done for both cities from the USGS 1 m height map. Cincinnati: 17.4% of path segments have a stretch steeper than the ADA ramp limit (8.33%), versus 5.3% in Oxford.
