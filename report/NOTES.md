# Report notes

Built from the `submission` branch (commit d496676), read from a `git archive` export, so nothing in the repo or its dirty working tree was touched.

Rebuild:
```
git archive submission | tar -x -C <dir>
<repo>/.venv/bin/python report/make_figures.py --repo <dir>     # numbers, tables, figures, runs report/search_bench.js
python3 report/build_report.py                                  # report.docx
report/export_pdf.sh                                            # report.pdf (needs Microsoft Word on macOS)
```
`template_transitional.docx` is the course template re-saved by Word, because the original is strict OOXML and python-docx cannot open it.

## Things for you to do (placeholders)
1. Author block (name, department, organisation, city, email): marked `[PLACEHOLDER ...]`.
2. Generative-AI statement: placeholder paragraph at the end of "AI Model and Implementation". Confirm or edit it.
3. Check the course's wording for the AI-use statement and where it must go.
4. No `[TODO: needs measurement]` items remain: every number was computed or copied from a result file.

## Numbers and where they come from
| Number in report | Source |
|---|---|
| 20 golden pairs, 16 routed, 1 same-point, 15 informative, 4 refusals | `tests/golden_routes_oxford.json`; `results/routing.json` (n_pairs, n_routes, n_informative, refusals) |
| Stairs 8 to 0, steep 12 to 6, road without sidewalk 7,130 to 564 m, length 19,164 to 19,813 m, crossings 61/89/79, unmarked 29/20/11, signals 9/20/24 | `results/routing.json` (computed by `make_figures.py`, networkx on the sample graph). Stairs, steep, road and length totals match `eval/results/routing_comparison.json` |
| Median extra 47 m (2.6%), mean 43, max 132; blind median 30, mean 41, max 136 | `results/routing.json` |
| Ogden Hall to Bishop Hall 350 m / 455 m, +105 m (30%), 55 m road | `results/routing.json` (per_route) |
| A* vs Dijkstra: equal cost on 30 searches, 864 vs 6108 pops, 3.8x / 2.9x, 0.12 / 0.17 ms, 20 ms graph build | `results/search_bench.json` from `search_bench.js` (Node v22.23.4, Apple M1, 8 GB); aggregated in `results/routing.json` (search) |
| Admissibility: 0 violations in 170,320 pairs per profile, max h/true cost 0.981 / 0.883; shortest edge ratio 0.9985 | `results/routing.json` (admissibility); 8 random goals, seed 486 |
| Heuristic ratio r = 1 (wheelchair), 0.90 (blind) | `search_bench.json` (heuristic_ratio) |
| Cost penalties (x6, x1.6, x3, x1.4, x2, x4, crossing 1/1.3/2/3.5, x0.9) | `src/atlas/routing.py` (`penalty`, `blind_penalty`) |
| Graph: 21,637 nodes, 25,436 edges (25,425 after parallel-edge drop), 153 stair edges, 99.0% with grade, 1.2% over 8.33%, 1 raised-kerb node, 8 sound=yes edges | `sample/oxford/walk_*.parquet` via `results/sources.json`; 25,425 from `search_bench.json`; kerb and sound counts from my own one-off pandas check (not in a saved file) |
| Table I counts, trust tiers 49 A / 10 B / 5 D of 64 cards | `data/cards/index.csv` via `results/sources.json` |
| DC fusion: 10,477 OSM kerbs, 89.1% corroborated, 27.7% coverage of 34,572 | `data/cards/agreement_dc.json` (copied to `results/`) |
| Trust weights and tiers | `config/trust.yaml` |
| Assistant tables (54/58, 39/45, 46/54, 54/55, 18/18, 171/174, 3 removed, 0.04 s; B to D columns) | `eval/results/agent_2026-11-23_submission.md` (A) and `eval/results/agent_2026-11-20.md` (B to D), parsed into `results/assistant_tables.json` |
| 174 questions = 44 + 55 + 57 + 18; A fails 17 | same files; `eval/*.yaml` counts verified |
| JS tests 44/44 pass | I ran `node --test tests/js/routing.test.js` on the exported branch |
| 288/300 random parity cases, zero-length-edge NaN bug | `docs/work_logs/routing.md` (not re-run by me; the report says so) |

## Differences from the repo's own docs
- Repo `routing_comparison` reports extra distance mean 40.5 / median 38.8 m. That includes the zero-length same-point pair. I use the 15 informative routes: mean 43.3, median 47.0.
- `docs/results_tables.md` rounds road-without-sidewalk to 565 m; I print 564 (564.5 rounds to even).
- Repo README says 5.3% of Oxford path sections exceed 8.33%. That is a different unit (slope-sample sections). I report 1.2% of walking-graph edges instead and did not use the README figure.
- `data/cards/index.csv` lists `osm_walk_network` as "not collected yet", although the walk graph exists. The card looks stale. I count it among the 5 tier-D cards and describe those as "not yet collected".

## Claims I am unsure about or could not fully verify
- ADA 1:12 and 1:20: the reference check was done through a summarising fetch of access-board.gov/ada. Please re-open sections 405.2 and 403.3 and confirm. I did not quote the text. Check the reference title too ("ADA Accessibility Standards" is my wording).
- The Oxford raised-kerb and audible-signal claims describe the Oxford sample graph only.
- "Remaining 6 steep sections cannot be avoided": not tested; the report says so.
- "Sidewalk penalty applies to every metre of a long road" as the reason for the biggest effect, and "no spelling correction in the planner" as the reason for the typo failure: both are marked in the text as likely or untested.
- Variants B to D: scored with the old trap checker (13/18, 15/18, 13/18 understated); not re-run (needs Ollama, about 1 h). The 44-question sample is tiny. Their timings ran while another job was using the machine.
- All hazard counts come from the same map data the router uses, so they cannot show hazards the map lacks. Nothing was checked on site.
- Qwen2.5 reference cites the technical report, not the exact quantised `qwen2.5:3b` build served by Ollama.
- Leaflet reference is the website; the project pins v1.9.4.
- The Bolten et al. reference is an arXiv preprint (not peer reviewed). Drop it if your course needs peer-reviewed sources only.
- The Cincinnati 311 portal page was opened but showed no description text; it is cited by title and URL.
- Table III uses counts, with percentages in the repo files. Table II omitted the queue-pop row, which is in the text and Fig. 2(b).

## Optional things left out
- `docs/figures/atlas_overview.png` (maps of Cincinnati) is not used. It did not fit the 6-page budget and shows Cincinnati data analysis rather than the two AI components.
- Browser timings (`scripts/measure_routing.py`, needs Playwright and a server) were not run; Node timings are used and labelled as such.
- Cincinnati routing was not evaluated (no golden file for it).
