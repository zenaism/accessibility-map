#!/usr/bin/env python
"""Build report/report.docx from the course template and the numbers in report/results/*.json.

    python3 report/build_report.py            (needs python-docx; run make_figures.py first)

The template is strict-OOXML, which python-docx cannot open, so report/template_transitional.docx is the same file
re-saved by Word as a standard .docx (styles, numbering, columns and footers unchanged).
Text carries [[key]] citation markers; numbers are filled from results/*.json so text and tables cannot drift apart.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results/routing.json").read_text())
SRC = json.loads((HERE / "results/sources.json").read_text())
AS = json.loads((HERE / "results/assistant_tables.json").read_text())
DC = json.loads((HERE / "results/agreement_dc.json").read_text())
OG = next(r for r in R["per_route"] if r["label"] == "Ogden Hall -> Bishop Hall")

wc, bl, sh, se = R["wheelchair"], R["blind"], R["shortest"], R["search"]
adm = R["admissibility"]
A23, ABCD = AS["A_2026-11-23"], AS["ABCD_2026-11-20"]
K_INT = "understood intent (new + trap questions with an intent)"
K_RET = "retrieval@5, expected place among top results"
K_HON = "honesty: unknown when data has no answer, answer when it has (bank + no-data categories)"
K_CON = "content checks (include/exclude) (new questions)"
K_TRAP = "trap pass rate"
K_VER = "answers fully verified (no sentence removed)"
K_REM = "sentences removed by the verifier (total)"
K_SEC = "seconds per answer, median / mean / max"


def pct(x):
    return f"{x:.1f}"


# ------------------------------------------------------------------ references (verified; order set by first citation)
REFS = {
    "osm": "OpenStreetMap contributors, “Copyright and license,” OpenStreetMap Foundation. [Online]. Available: https://www.openstreetmap.org/copyright. Accessed: Nov. 23, 2026.",
    "usgs": "U.S. Geological Survey, “3D Elevation Program (3DEP).” [Online]. Available: https://www.usgs.gov/3d-elevation-program. Accessed: Nov. 23, 2026.",
    "cagis": "Cincinnati Area Geographic Information System (CAGIS). [Online]. Available: https://www.cagis.org. Accessed: Nov. 23, 2026.",
    "dijkstra": "E. W. Dijkstra, “A note on two problems in connexion with graphs,” Numerische Mathematik, vol. 1, no. 1, pp. 269–271, 1959, doi: 10.1007/BF01386390.",
    "hart": "P. Hart, N. Nilsson, and B. Raphael, “A formal basis for the heuristic determination of minimum cost paths,” IEEE Trans. Syst. Sci. Cybern., vol. 4, no. 2, pp. 100–107, 1968, doi: 10.1109/TSSC.1968.300136.",
    "ada": "U.S. Access Board, “ADA Accessibility Standards” (sections 403.3 and 405.2). [Online]. Available: https://www.access-board.gov/ada/. Accessed: Nov. 23, 2026.",
    "neis": "P. Neis, “Measuring the reliability of wheelchair user route planning based on volunteered geographic information,” Transactions in GIS, vol. 19, no. 2, pp. 188–201, 2015, doi: 10.1111/tgis.12087.",
    "bolten": "N. Bolten, A. Amini, Y. Hao, V. Ravichandran, A. Stephens, and A. Caspi, “Urban sidewalks: Visualization and routing for individuals with limited mobility,” arXiv:1602.04281, 2016 (preprint).",
    "saha": "M. Saha et al., “Project Sidewalk: A web-based crowdsourcing tool for collecting sidewalk accessibility data at scale,” in Proc. CHI Conf. Human Factors in Computing Systems (CHI '19), Glasgow, U.K., 2019, doi: 10.1145/3290605.3300292.",
    "tannert": "B. Tannert, R. Kirkham, and J. Schöning, “Analyzing accessibility barriers using cost-benefit analysis to design reliable navigation services for wheelchair users,” in Human-Computer Interaction – INTERACT 2019, Lecture Notes in Computer Science, 2019, pp. 202–223, doi: 10.1007/978-3-030-29381-9_13.",
    "lewis": "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Advances in Neural Information Processing Systems 33 (NeurIPS 2020), arXiv:2005.11401.",
    "overture": "Overture Maps Foundation, “Places.” [Online]. Available: https://docs.overturemaps.org/guides/places/. Accessed: Nov. 23, 2026.",
    "c311": "City of Cincinnati, “Cincinnati 311 (Non-Emergency) Service Requests,” Cincinnati Open Data Portal. [Online]. Available: https://data.cincinnati-oh.gov/Innovative-Government/Customer-Service-Requests-CSRs-/gcej-gmiw. Accessed: Nov. 23, 2026.",
    "gtfs": "“GTFS Schedule Reference.” [Online]. Available: https://gtfs.org/documentation/schedule/reference/. Accessed: Nov. 23, 2026.",
    "scipy": "P. Virtanen et al., “SciPy 1.0: Fundamental algorithms for scientific computing in Python,” Nature Methods, vol. 17, no. 3, pp. 261–272, 2020, doi: 10.1038/s41592-019-0686-2.",
    "networkx": "A. A. Hagberg, D. A. Schult, and P. J. Swart, “Exploring network structure, dynamics, and function using NetworkX,” in Proc. 7th Python in Science Conf. (SciPy 2008), G. Varoquaux, T. Vaught, and J. Millman, Eds., 2008, pp. 11–15, doi: 10.25080/TCWV9851.",
    "duckdb": "M. Raasveldt and H. Mühleisen, “DuckDB: An embeddable analytical database,” in Proc. 2019 Int. Conf. Management of Data (SIGMOD '19), Amsterdam, The Netherlands, 2019, pp. 1981–1984, doi: 10.1145/3299869.3320212.",
    "qwen": "Qwen Team, “Qwen2.5 technical report,” arXiv:2412.15115, Dec. 2024.",
    "ollama": "Ollama. [Online]. Available: https://github.com/ollama/ollama. Accessed: Nov. 23, 2026.",
    "leaflet": "“Leaflet: an open-source JavaScript library for interactive maps.” [Online]. Available: https://leafletjs.com/. Accessed: Nov. 23, 2026.",
    "mpl": "J. D. Hunter, “Matplotlib: A 2D graphics environment,” Computing in Science & Engineering, vol. 9, no. 3, pp. 90–95, 2007, doi: 10.1109/MCSE.2007.55.",
}

# ------------------------------------------------------------------ text.  ("h1"/"h2"/"p"/"fig"/"table", ...)
TITLE = "Accessibility Map: Cost-Aware A* Routing and an Evidence-Grounded Assistant for Wheelchair and Blind Travellers"

ABSTRACT = (
    "Abstract—A router that minimises distance sends a wheelchair user up stairs and steep slopes, because those cost the same as flat ground. "
    "Accessibility Map fuses open data for Oxford and Cincinnati, Ohio (OpenStreetMap, USGS elevation, city records, venue websites) and adds two AI components. "
    "The core one is an A* search whose edge costs encode accessibility rules: stairs are forbidden, slopes above the Americans with Disabilities Act (ADA) ramp limit of 8.33% cost six times their length, and roads with no mapped sidewalk cost 1.4 to 3 times. "
    f"These penalties are set by hand, not learned. On {R['n_informative']} informative golden routes in Oxford, the step-free route removes all {sh['stairs']} stair sections and half of the {sh['steep']} steep sections that the shortest path uses, "
    f"for a median detour of {wc['extra_median']:.0f} m ({pct(wc['extra_pct_median'])}%). A* returns the same cost as Dijkstra's algorithm on all {se['n_searches']} searches while taking a median {se['wheelchair']['pops_ratio_median']} times fewer queue pops. "
    "The second component is a rule-based assistant over a DuckDB knowledge base, with an optional local language model, in which a verifier keeps only sentences tied to a record. "
    f"On 174 self-written questions it passes 18 of 18 trap tests, but the question bank was written by the author after seeing the data, so these are regression numbers, not accuracy."
)
KEYWORDS = "Keywords—A* search, accessibility, wheelchair routing, OpenStreetMap, knowledge-based AI, grounded question answering"

fam = SRC["families"]


def fmt(n):
    return "–" if not n else f"{n:,}"


TABLE1 = {
    "caption": "Data sources used for Oxford and Cincinnati, Ohio: records per source (from the dataset cards)",
    "head": ["Source", "Oxford", "Cincinnati"],
    "rows": [[k, fmt(v["oxford"]), fmt(v["cincinnati"])] for k, v in fam.items()],
    "note": "Records after each connector's own filtering; web sources count pages or documents. Slope records are path sections with an elevation-based grade.",
}

TABLE2 = {
    "caption": f"Routing on the golden Oxford routes ({R['n_informative']} informative routes; sums unless stated)",
    "head": ["Measure", "Shortest", "Wheelchair", "Blind"],
    "rows": [
        ["Stair sections", sh["stairs"], wc["stairs"], bl["stairs"]],
        ["Steep sections (>8.33%)", sh["steep"], wc["steep"], bl["steep"]],
        ["Road, no sidewalk (m)", f"{sh['road_no_sidewalk_m']:,.0f}", f"{wc['road_no_sidewalk_m']:,.0f}", f"{bl['road_no_sidewalk_m']:,.0f}"],
        ["Street crossings", sh["crossings"], wc["crossings"], bl["crossings"]],
        ["  of which unmarked or unmapped", sh["crossings_unmarked"], wc["crossings_unmarked"], bl["crossings_unmarked"]],
        ["  of which with signals", sh["crossings_signals"], wc["crossings_signals"], bl["crossings_signals"]],
        ["Total length (m)", f"{sh['length_m']:,.0f}", f"{wc['length_m']:,.0f}", f"{bl['length_m']:,.0f}"],
        ["Extra distance, median (m)", "–", f"{wc['extra_median']:.0f}", f"{bl['extra_median']:.0f}"],
        ["Extra distance, mean / max (m)", "–", f"{wc['extra_mean']:.0f} / {wc['extra_max']:.0f}", f"{bl['extra_mean']:.0f} / {bl['extra_max']:.0f}"],
        ["Route differs from shortest", "–", f"{wc['differs_from_shortest']} of {R['n_informative']}", f"{bl['differs_from_shortest']} of {R['n_informative']}"],
        ["A* search, median (ms)", "–", f"{se['wheelchair']['astar_ms_median']:.2f}", f"{se['blind']['astar_ms_median']:.2f}"],
    ],
    "note": "Search times are from Node.js on an Apple M1, not from a browser. Plain shortest path allows stairs.",
}


def cell(d, key):
    return d[key][0]


def t3col(key, abcd_i):
    return ABCD[key][abcd_i]


TABLE3 = {
    "caption": "Assistant evaluation. A: rules only, all 174 questions. B: model plans. C: model writes. D: both (B to D: 44-question sample)",
    "head": ["Metric", "A", "B", "C", "D"],
    "rows": [
        [lab] + [cell(A23, k).split(" = ")[0]] + [ABCD[k][i].split(" = ")[0] for i in (1, 2, 3)]
        for lab, k in (
            ("Understood intent", K_INT),
            ("Retrieval@5", K_RET),
            ("Honesty (answer or unknown)", K_HON),
            ("Content checks", K_CON),
            ("Trap tests passed*", K_TRAP),
            ("Fully verified answers", K_VER),
            ("Sentences removed", K_REM),
        )
    ]
    + [["Seconds per answer, median", A23[K_SEC][0].split(" / ")[0]] + [ABCD[K_SEC][i].split(" / ")[0] for i in (1, 2, 3)]],
    "note": "*B to D were scored with an earlier trap checker that wrongly failed correct refusals; rules-only A scored 15/18 with it and 18/18 after the fix. B to D were not re-run.",
}

CONTENT = [
    ("h1", "Introduction"),
    ("p", f"A plain shortest-path router minimises distance. That is fine for someone who can step over a kerb and fails for a wheelchair user, because a flight of stairs costs the same as a flat footpath of the same length, and a 12% slope looks like any other 30 metres. People with low vision face a different version of the problem: the short way may cross a busy street at an unmarked spot (on my test routes, {sh['crossings_unmarked']} of the {sh['crossings']} crossings on shortest paths are unmarked or not mapped). The data needed to do better exists in pieces. OpenStreetMap (OSM) [[osm]] maps stairs, kerbs and crossings, the U.S. Geological Survey (USGS) publishes elevation through its 3D Elevation Program (3DEP) [[usgs]], and Cincinnati keeps a city inventory of curb ramps and sidewalks [[cagis]]."),
    ("p", "This project, Accessibility Map, fuses those sources for Oxford and Cincinnati, Ohio, and adds two AI components (Fig. 1). The core one is route search. Dijkstra's algorithm [[dijkstra]] finds the cheapest path in a graph by always expanding the node with the lowest cost so far. A* [[hart]] adds an estimate of the cost still to go, so it expands fewer nodes and still returns the cheapest path as long as the estimate never overshoots. The AI content is in the cost function, which turns accessibility rules, such as the ADA slope limits [[ada]], into penalties. This is knowledge-based search, not machine learning. The penalties are my own judgement and nothing is trained."),
    ("fig", "fig1_pipeline.png", "System overview. Solid boxes are what the route search and the assistant run on; the dashed box is reported per source and not read by either."),
    ("p", "The second component is an assistant that answers questions such as “can I borrow an all-terrain wheelchair at any park around here?” from a knowledge base of sourced records. It is rule-based by default. An optional local language model can be switched on, and every sentence, however it was written, passes a verifier that deletes anything it cannot tie to a record. An answer that invents a ramp is worse than no answer."),
    ("p", "Wheelchair routing on volunteered map data is not new. Neis built a router on OSM and added a reliability score for how far a computed path can be trusted [[neis]]. Bolten et al. combine sidewalk, curb-ramp and elevation layers into a graph with variable cost functions [[bolten]], and Project Sidewalk crowdsources the missing sidewalk data from street-view labels [[saha]]. A caution comes from Tannert et al., who found that accessibility routers were not significantly more likely than a general pedestrian router to return an accessible route, in part because of barriers in the data that do not exist on the ground [[tannert]]. My router inherits that risk, and I can only measure it as far as the map data allows."),
    ("p", f"The questions are narrow. On real Oxford routes, does a hand-built accessibility cost remove hazards for a small detour, and does A* stay exact and fast? Can the assistant tie answers to records and say “I don't know” when the data runs out? On {R['n_informative']} informative routes the step-free route removes all {sh['stairs']} stair sections and half of the {sh['steep']} steep sections for a median detour of {wc['extra_median']:.0f} m. A* matches Dijkstra's cost on all {se['n_searches']} searches. The rules-only assistant passes all 18 trap tests, but I wrote the questions, so those numbers are a regression check and not an accuracy score."),

    ("h1", "Methodology"),
    ("h2", "Data and Preprocessing"),
    ("p", f"Table I lists the sources. The assistant draws on all of them, while the router uses only the OSM walking graph and slope. Besides OSM, the sources are Overture Maps places [[overture]], four Cincinnati Area Geographic Information System (CAGIS) layers [[cagis]], Cincinnati 311 service requests [[c311]], General Transit Feed Specification (GTFS) bus stops [[gtfs]] and venue websites. Each source comes through a connector that records its licence, URL and retrieval date and produces a dataset card. Facts from venue sites are stored with a word-for-word quote and a link, so an answer can show where it came from, and pages whose robots.txt forbids bots are skipped. Oxford has no curb-ramp or 311 layer in this project, so those exist for Cincinnati only."),
    ("table", TABLE1),
    ("p", f"The router's input is a walking graph from OSM footways, sidewalks, crossings and paths. For Oxford it has {SRC['oxford_walk_nodes']:,} nodes and {SRC['oxford_walk_edges_parquet']:,} edges ({se['graph_edges']:,} after dropping 11 parallel edges), {SRC['oxford_stair_edges']} of them stairs. Each edge has its length in metres and the tags that matter: sidewalk, surface, crossing type, signals, sound or vibration, tactile paving. A raised kerb is stored on the node. The slope of each edge is estimated from USGS 3DEP elevation [[usgs]]. {SRC['oxford_edges_with_grade']:,} edges ({100 * SRC['oxford_edges_with_grade'] / SRC['oxford_walk_edges_parquet']:.1f}%) have a grade, and {SRC['oxford_edges_grade_gt_8_33_pct']}% of all edges are steeper than 8.33%. Nothing was checked on the ground, so every slope, stair and missing sidewalk in this report is what the map says."),
    ("p", f"Fusion matches records from different sources by position, using a k-d tree nearest-neighbour query [[scipy]] with a distance tolerance. I use it to measure how far two sources agree, not to merge them into one record. The one pair I computed is Washington, DC, where an official curb-ramp inventory exists. Of {DC['curb_ramps']['osm_lowered_or_flush']:,} OSM kerbs tagged lowered or flush, {100 * DC['curb_ramps']['osm_corroboration']:.1f}% lie within {DC['curb_ramps']['tolerance_m']:.0f} m of an inventory ramp, but OSM contains only {100 * DC['curb_ramps']['osm_coverage_of_inventory']:.1f}% of the {DC['curb_ramps']['inventory_ramps']:,} inventory ramps. What OSM says is mostly right and what it leaves out is most of the picture. The router makes the same distinction: a road whose sidewalk is not mapped is treated as unknown (a 1.4 times penalty) and a road tagged with no sidewalk as bad (3 times)."),
    ("p", f"Each source also gets a trust score from 0 to 100, a weighted mean of seven components: authority, provenance, freshness, completeness, quality, agreement with other sources and track record. The weights are 0.25, 0.10, 0.15, 0.15, 0.15, 0.10 and 0.10, and a component that cannot be measured is dropped and the rest rescaled. Scores map to tiers A (80 and above), B (50 and above), C (30 and above) and D (below 30). The weights are starting guesses that I never tuned, because there is no reference data to tune on. The outcome is blunt: {SRC['tiers_all_64']['A']} of {SRC['n_cards']} dataset cards landed in tier A, {SRC['tiers_all_64']['B']} in B and {SRC['tiers_all_64']['D']} in D (sources not yet collected). The score separates good from absent and little else. Neither the router nor the assistant reads it."),
    ("p", "No model is trained, so there is no training, validation and test split and no leakage in the usual sense. The test material is a set of 20 routes and 174 questions that I wrote after looking at the data, which matters for how the results should be read."),

    ("h2", "AI Model and Implementation"),
    ("p", f"<i>A* and the heuristic.</i> A route is a path in the walking graph, and each edge has a cost. A* keeps a queue of nodes ordered by f(n) = g(n) + h(n), where g(n) is the cheapest cost found so far from the start to n and h(n) estimates the cost from n to the goal. With h = 0 this is Dijkstra's algorithm. If h never overestimates the true remaining cost, it is called admissible, and then the first time A* removes the goal from the queue its path is a cheapest one [[hart]]. A good h steers the search toward the goal, so fewer nodes are expanded."),
    ("p", f"My heuristic is h(n) = 0.98 r d(n), where d(n) is the straight-line distance to the goal and r is the lowest cost-to-length ratio of any edge in the graph. Any path from n to the goal is at least d(n) long and every metre costs at least r, so h cannot overshoot. For the wheelchair profile r is {se['heuristic_ratio']['wheelchair']:.0f}, because an ordinary footway has no penalty. For the blind profile r is {se['heuristic_ratio']['blind']:.2f}, because crossings with tactile paving are discounted by 0.9. The 0.98 factor is slack. Edge lengths come from geodesic distance while d(n) is measured on a flat projection, and some stored edge lengths are as low as {adm['edge_len_over_straight_min']:.4f} times the straight-line distance between their ends, so without slack the bound could be broken by a hair. I checked admissibility directly: for 8 random goals and both profiles I computed exact least costs to every reachable node with Dijkstra and compared them with h. There were {adm['checks']['wheelchair']['violations']} violations in {adm['checks']['wheelchair']['pairs_checked']:,} node and goal pairs per profile, and the largest h was {100 * adm['checks']['wheelchair']['max_h_over_true_cost']:.1f}% of the true cost for the wheelchair profile ({100 * adm['checks']['blind']['max_h_over_true_cost']:.1f}% for blind). One bug is worth recording. Some Cincinnati edges have length zero, which made the ratio r undefined, the heuristic became not-a-number (NaN) and the router returned wrong, much longer paths. Zero-length edges are now skipped when r is computed, and a unit test covers it."),
    ("p", "<i>The cost function.</i> The edge cost is its length in metres times a penalty. Stairs cost infinity, so a route never uses them and the router returns “no step-free route” when stairs are the only link. A slope steeper than 8.33% (1:12, the ADA limit for a ramp) multiplies the cost by 6, and one between 5% and 8.33% by 1.6, where 5% (1:20) is the ADA limit above which a walking surface counts as a ramp [[ada]]. A road with sidewalk=no costs 3 times, a road whose sidewalk is simply not mapped 1.4 times, a rough surface 2 times and a raised kerb at either end 4 times. Fig. 2(a) plots the slope part. The blind profile also scales crossings: 1.0 with an audible or vibrating signal, 1.3 for a signal without sound, 2.0 for a marked crossing without a signal and 3.5 for an unmarked or unmapped one, times 0.9 with tactile paving."),
    ("fig", "fig4_cost_and_search.png", "(a) Slope penalty used in the cost function. (b) Search work per route, counted as nodes taken from the priority queue, for A* and for Dijkstra on the same weights."),
    ("p", "Why not just take the shortest path? Because distance is the wrong thing to minimise. A shortest path is optimal for someone who can step over a kerb. For a wheelchair user a stair is a wall and a steep slope is an effort or a danger, and neither grows in proportion to its length. The multipliers say how many extra metres I am willing to walk to avoid a metre of a bad edge: a steep section costs six times its length, so the router accepts up to five extra metres per metre avoided. These numbers are hand-set. I borrowed the ADA thresholds, which apply to ramps and walkways on accessible routes, for individual sections of sidewalk, and I never fitted any multiplier to data or to how wheelchair users actually choose routes. The “missing ramp” penalty is only the raised-kerb tag, which is what OSM can say."),
    ("p", f"<i>Implementation.</i> The cost rules live in Python (routing.py), which also exports the graph. The browser runs the search in JavaScript (routing.js) with its own binary heap, so no routing library is shipped to the page. The Python reference answers with networkx's shortest-path routine [[networkx]], which is Dijkstra's algorithm, so the A* itself exists only in the JavaScript. I therefore test the two against each other: all 20 golden pairs for both profiles reproduce the Python paths node for node in the JavaScript tests (44 of 44 tests pass, which I re-ran), and a separate run on 300 random cases (150 node pairs, both profiles) gave 288 identical results and 12 with no route in both, according to the project's work log, which I did not repeat. Edge costs are rounded to 0.1 mm so that the two sums agree."),
    ("p", f"<i>The assistant.</i> A question goes through four steps (Fig. 1). A rules planner reads it in a fixed order: emergency words first (it answers “call 911” and stops), then help requests, then trust questions such as “is this ADA compliant?”, out-of-area questions, categories with no data, live information that a snapshot cannot give, and finally events, routes and places by need. An executor runs tools (search_places, nearest, get_place, find_events, plus route and area lookups) over a DuckDB database [[duckdb]]. A composer fills templates with the results. The verifier then keeps a sentence only if it cites a record that exists, contains no banned phrase (“ADA compliant”, “safe”, “guaranteed”), and every number, quoted string and capitalised name in it appears in the results or the question. If nothing survives, the answer becomes “I don't know”. It is a string-level check on support, not a judgement of relevance. This is close in spirit to retrieval-augmented generation [[lewis]], except that the generator is optional and a rule checks its output."),
    ("p", "The optional model is Qwen2.5 3B [[qwen]] served by Ollama [[ollama]], and it has two jobs. It can read a question and fill slots (intent, need, place) under a JavaScript Object Notation (JSON) schema, which the rules then validate and plan from, or it can write the one or two headline sentences from the tool results, which then go through the same verifier. Emergency, trust and no-data questions never reach it. With the model off, which is the default, the system makes no model calls."),
    ("p", "<i>Tools and use of generative AI.</i> The code is Python 3.12 (pandas, networkx, SciPy, DuckDB) and JavaScript, the map page uses Leaflet 1.9.4 [[leaflet]] with a USGS basemap, and the figures are drawn with Matplotlib [[mpl]]. [PLACEHOLDER, please confirm and edit: I used Claude Code (Anthropic) to help build and document parts of the project and to help draft this report. I reviewed and checked the content, and the numbers in the report come from scripts and result files in the project repository.]"),

    ("h2", "Experimental Setup"),
    ("p", f"<i>Routing.</i> The test set is 20 golden Oxford routes in the repository. A script picks them deterministically from mapped places to cover each kind of route: routes that avoid stairs (3), steep sections (2), many crossings (3), different blind and wheelchair routes (2), a road without sidewalk, two short routes, a long route, one where the shortest path is already the easiest, two with no step-free route, a same-point pair and two with an end farther than 150 m from any path. Sixteen return a route, one of them same-point, so {R['n_informative']} are informative. The four others are negative cases, and the router correctly returns nothing for all four. The baseline is the plain shortest path by length on the same graph, with the same snapping and with stairs allowed. For every route I count, from the edge attributes along each path: stair sections, sections steeper than 8.33%, metres of road without a mapped sidewalk, and street crossings by type, plus length. Extra distance is the step-free length minus the shortest length. Because the hazards are counted from the same data the router optimises, “hazards avoided” can only mean hazards the map records. Timing is from Node.js {se['node_version']} on an Apple M1 with 8 GB of memory, the median of 15 repeats per search, and counts the nodes taken from the queue; browser timings are not included."),
    ("p", "<i>Assistant.</i> The 174 questions are 44 from an original bank, 55 written later, 57 category questions with no expected answers and 18 traps (ADA claims, safety, prompt injection planted in a record, role play, medical advice). The metrics are: whether the planner found the right intent; retrieval@5, meaning the expected place is among the first five results; honesty, meaning the assistant says it does not know when the data has no answer and answers when it has one; include and exclude string checks on the text; the share of trap tests passed; and the share of answers in which the verifier removed nothing. Variant A is rules and templates. B lets the model plan, C lets it write the headline sentences, and D does both. A ran on all 174 questions on 23 November 2026 with the date fixed at 20 November. B to D ran on 20 November on a sample of 44 questions (every sixth plus all traps) with Qwen2.5 3B on the same 8 GB M1 while another job was running, because a model answer takes seconds to minutes; the timings are therefore pessimistic."),

    ("h1", "Experimental Results"),
    ("p", f"<i>An example.</i> Fig. 3 shows one real Oxford route, Ogden Hall to Bishop Hall. The shortest path is {OG['shortest_length_m']:.0f} m and crosses one stair section and one slope steeper than 8.33%. The step-free route is {OG['wheelchair_length_m']:.0f} m, which is {OG['extra_m']:.0f} m ({OG['extra_m'] / OG['shortest_length_m'] * 100:.0f}%) longer, the biggest relative detour in the set. It is also the only route where the step-free path is worse on any hazard: it walks {OG['wheelchair_road_no_sidewalk_m']:.0f} m on a road with no mapped sidewalk, where the shortest path walks none. With stairs forbidden, that was the cheapest way around, and I think it is the honest outcome. A router that hides such trade-offs would be worse."),
    ("fig", "fig2_route_map.png", "Ogden Hall to Bishop Hall, Oxford, Ohio, on the OSM walking graph. Hazards are marked on the shortest path; white dashes mark road with no mapped sidewalk. Not checked on site."),
    ("p", f"<i>Routing against the baseline.</i> Table II sums the {R['n_informative']} informative routes. The step-free route differs from the shortest path on {wc['differs_from_shortest']} of them. It uses none of the {sh['stairs']} stair sections the shortest path crosses and {wc['steep']} of {sh['steep']} steep sections, and it cuts the road walked without a sidewalk from {sh['road_no_sidewalk_m']:,.0f} m to {wc['road_no_sidewalk_m']:,.0f} m. The price is {wc['length_m'] - sh['length_m']:,.0f} m over {sh['length_m']:,.0f} m in total, a median of {wc['extra_median']:.0f} m ({pct(wc['extra_pct_median'])}%) per route and at most {wc['extra_max']:.0f} m. The six steep sections that remain sit on two routes through Peffer Park (three each). I did not test whether they are unavoidable on the mapped network, for example by forbidding steep sections, so I cannot say whether the 6 times penalty was too soft or the map left no choice. Raised kerbs are zero on every route: the Oxford graph has a single raised-kerb node and no route touches it, so this data cannot show missing ramps avoided."),
    ("table", TABLE2),
    ("p", "Fig. 4(a) shows the hazards avoided against the distance paid. Eight of the 15 routes avoid at least one stair or steep section, and they pay between 30 and 132 m for it. The two routes that avoid three hazards cost 132 m (Yager Stadium to SDS Pizza) and 55 m (Walter L. Gross Center to Yum Cha). Four routes pay 8 to 57 m and avoid no stair or steep section at all; what they gain is in Fig. 4(b), where nine routes shed more than 300 m of road walked without a mapped sidewalk. That is the largest change in Table II, 92% of the road metres against 50% of the steep sections. I did not expect it. A likely reason is that the sidewalk penalty applies to every metre of a long road, while a steep section is a few short edges."),
    ("fig", "fig3_hazards_vs_distance.png", "(a) Stair and steep sections avoided against extra distance, one dot per route. (b) Metres of road walked without a mapped sidewalk, plain shortest path against step-free route."),
    ("p", f"<i>The blind profile.</i> The wheelchair and blind routes are identical on {R['wheelchair_path_equals_blind_path']} of {R['n_informative']} routes. Over all routes the blind profile walks more on roads, {bl['road_no_sidewalk_m']:,.0f} m against {wc['road_no_sidewalk_m']:,.0f} m, in return for fewer unmarked or unmapped crossings ({bl['crossings_unmarked']}, against {wc['crossings_unmarked']} for the wheelchair route and {sh['crossings_unmarked']} for the shortest path) and more signalised ones ({bl['crossings_signals']}). The step-free route has more crossings than the shortest path ({wc['crossings']} against {sh['crossings']}), which surprised me. Staying on sidewalks probably means switching sides of the street more often. The preference for audible signals had almost nothing to act on, since {sh['crossings_audible']} crossing on all shortest paths and {bl['crossings_audible']} on the blind routes carries a sound or vibration tag. Only 8 edges in the whole Oxford graph carry sound=yes, so in Oxford that preference is a feature waiting for data."),
    ("p", f"<i>Search.</i> A* returned the same cost as Dijkstra on all {se['n_searches']} searches (15 routes, 2 profiles), and the same path every time. It took a median of {se['wheelchair']['astar_pops_median']:.0f} nodes from the queue against {se['wheelchair']['dijkstra_pops_median']:.0f} for the wheelchair profile, {se['wheelchair']['pops_ratio_median']} times fewer in the median route (Fig. 2(b)), and {se['blind']['pops_ratio_median']} times fewer for the blind profile, whose heuristic is weaker because r is 0.90. A search takes a median of {se['wheelchair']['astar_ms_median']:.2f} ms (at most {se['wheelchair']['astar_ms_max']:.1f} ms) and building the in-memory graph takes {se['load_graph_ms']:.0f} ms. Oxford is small, {se['graph_nodes']:,} nodes, so even Dijkstra takes under a millisecond. What A* buys here is not a visible speed-up. Its work should matter more on a larger graph such as Cincinnati, which I have not timed."),
    ("p", f"<i>The assistant.</i> Table III gives the evaluation. The rules-only variant A understood the intent of {A23[K_INT][0].split(' = ')[0]} questions, found the expected place in the top five for {A23[K_RET][0].split(' = ')[0]}, and passed all 18 trap tests. Its honesty score is {A23[K_HON][0].split(' = ')[0]} ({A23[K_HON][0].split(' = ')[1]}), the weakest number in the table. The verifier removed 3 sentences in total and 171 of 174 answers needed no edit. Variant A fails 17 questions. Some are plain misses, such as “does the cincinati art musuem lend wheelchars”, probably because the rules planner has no spelling correction (I did not test that). Others are honesty failures where it says it does not know although a record exists, or the reverse. The model variants did not beat the rules. On the 44-question sample they score 14 of 14 on intent, and they are a question or two apart on retrieval and honesty, where only 8 questions decide each retrieval figure, so I read the differences as noise. They are more than a hundred times slower (medians of {ABCD[K_SEC][1].split(' / ')[0]}, {ABCD[K_SEC][2].split(' / ')[0]} and {ABCD[K_SEC][3].split(' / ')[0]} s against {A23[K_SEC][0].split(' / ')[0]} s), and the verifier removed 9 sentences from the 44 answers in C and 6 in D, against 3 from 174 answers in A, which is the verifier doing its job. Their trap scores are not comparable with A's (see Table III)."),
    ("table", TABLE3),

    ("h1", "Conclusion"),
    ("p", f"I built an A* router with a hand-set accessibility cost for Oxford and an evidence-grounded assistant over the same open data, and tested both against a baseline. On {R['n_informative']} informative golden routes the step-free route avoids every stair section and half the steep sections for a median detour of {wc['extra_median']:.0f} m, and A* returns exactly the cost Dijkstra does, with a heuristic that I checked against exact distances. The assistant, rules only, passes its 18 trap tests and answers in 0.04 s at the median, and a 3B local model added latency without a visible gain. The most useful things I learned came from failures: a zero-length edge broke the heuristic, the step-free route pays for avoiding stairs with road walking in one case, and the biggest change the router made was in road walking, not in slopes."),
    ("p", "The limits are real. The penalties are judgement and were never fitted or checked with wheelchair users. The 20 routes are mine, in one city, and the hazards are counted from the same map data the router optimises, so a hazard the map does not record is invisible to both. Oxford has one raised-kerb node and 8 sound-tagged edges, so two of the router's features could not be tested there. Nothing was checked on site, and Tannert et al. [[tannert]] show why that matters. The assistant's question bank and trap checker are my own, the verifier checks support and not relevance, and B to D rest on 44 questions with an outdated trap checker. Next steps are to compare routes against an independent field audit or Project Sidewalk labels [[saha]], to fit the penalties to route choices of real users, to have other people write the assistant's questions, and to use the Cincinnati curb-ramp inventory in the router, which the Oxford graph has no counterpart for."),
]


# ------------------------------------------------------------------ docx helpers
def set_runs(p, text, base_size=None):
    """Write text into paragraph p, with *italic* markup and [[key]] already resolved."""
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    for i, part in enumerate(re.split(r"</?i>", text)):
        if not part:
            continue
        run = p.add_run(part)
        if i % 2:
            run.italic = True
        if base_size:
            run.font.size = Pt(base_size)


def cite_numbers(texts):
    order = []
    for t in texts:
        for k in re.findall(r"\[\[([a-z0-9]+)\]\]", t):
            if k not in order:
                order.append(k)
    return order


def collect_texts():
    out = [ABSTRACT]
    for item in CONTENT:
        if item[0] == "p":
            out.append(item[1])
    return out


def build():
    doc = docx.Document(str(HERE / "template_transitional.docx"))
    ps = doc.paragraphs
    order = cite_numbers(collect_texts())
    missing = [k for k in order if k not in REFS]
    assert not missing, missing
    num = {k: i + 1 for i, k in enumerate(order)}
    unused = [k for k in REFS if k not in num]
    assert not unused, f"references never cited: {unused}"

    def resolve(t):
        return re.sub(r"\[\[([a-z0-9]+)\]\]", lambda m: f"[{num[m.group(1)]}]", t)

    # title, notes, author block
    set_runs(ps[0], TITLE)
    set_runs(ps[1], "")
    a = ps[2]
    for r in list(a.runs):
        r._r.getparent().remove(r._r)
    lines = ["Mariam Zenaishvili", "Department of Computer Science and Software Engineering", "Oxford, Ohio, USA", "zenaism@miamioh.edu"]
    for i, ln in enumerate(lines):
        run = a.add_run(ln)
        run.font.size = Pt(9)
        run.italic = i == 1
        if i < len(lines) - 1:
            run.add_break()
    cols = a._p.find(qn("w:pPr")).find(qn("w:sectPr")).find(qn("w:cols"))
    for k in list(cols.attrib):
        if k.endswith("}num"):
            del cols.attrib[k]
    # remove template author placeholders and sample text
    body_p = doc.paragraphs
    for p in body_p[3:18]:
        p._p.getparent().remove(p._p)
    body_p = doc.paragraphs  # [title, note, author, abstract, keywords, 20.. 43..]
    abstract, kw = body_p[3], body_p[4]
    set_runs(abstract, resolve(ABSTRACT))
    set_runs(kw, KEYWORDS)
    tail = body_p[5:]
    anchor = tail[-2]  # last template reference paragraph: carries the two-column section end
    for p in tail[:-2]:
        p._p.getparent().remove(p._p)

    def before(style):
        return anchor.insert_paragraph_before("", style=style)

    for item in CONTENT:
        kind = item[0]
        if kind == "h1":
            before("Heading 1").add_run(item[1])
        elif kind == "h2":
            before("Heading 2").add_run(item[1])
        elif kind == "p":
            set_runs(before("Body Text"), resolve(item[1]))
        elif kind == "fig":
            _, file, cap = item
            p = before("Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(4)
            p.add_run().add_picture(str(HERE / "figures" / file), width=Inches(3.4))
            c = before("figure caption")
            c.add_run(cap)
        elif kind == "table":
            t = item[1]
            h = before("table head")
            h.add_run(t["caption"])
            h.paragraph_format.keep_with_next = True
            tbl = doc.add_table(rows=1 + len(t["rows"]), cols=len(t["head"]))
            anchor._p.addprevious(tbl._tbl)
            tbl.alignment = 1
            for j, txt in enumerate(t["head"]):
                c = tbl.rows[0].cells[j]
                c.paragraphs[0].style = doc.styles["table col head"]
                c.paragraphs[0].add_run(str(txt))
            for i, row in enumerate(t["rows"], 1):
                for j, txt in enumerate(row):
                    c = tbl.rows[i].cells[j]
                    pp = c.paragraphs[0]
                    pp.style = doc.styles["table copy"]
                    pp.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
                    pp.add_run(str(txt))
            style_table(tbl)
            n = before("Normal")
            n.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            r = n.add_run(t["note"])
            r.font.size = Pt(7)
            n.paragraph_format.space_after = Pt(8)
    before("Heading 5").add_run("References")
    for i, k in enumerate(order):
        p = before("references") if i < len(order) - 1 else anchor
        if p is anchor:
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
        p.add_run(REFS[k])
    # first-page footer boilerplate
    for s in doc.sections:
        for f in (s.first_page_footer,):
            for p in f.paragraphs:
                for r in p.runs:
                    r.text = ""
    # last empty paragraph of the template, if any, stays as the final section break
    doc.save(str(HERE / "report.docx"))
    return order


def style_table(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, sz in (("top", 8), ("bottom", 8), ("insideH", 2)):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "808080")
        borders.append(e)
    tblPr.append(borders)
    for row in tbl.rows:
        trPr = row._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)
    for c in tbl.rows[0].cells:
        for p in c.paragraphs:
            p.paragraph_format.keep_with_next = True


if __name__ == "__main__":
    o = build()
    print("citations in order:", o)
