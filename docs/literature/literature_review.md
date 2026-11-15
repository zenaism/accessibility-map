# Literature Review: Wheelchair Accessibility Data, Sensing and LLMs

Nov 7, 2026 · @Mariam Zenaishvili

**The field can map sidewalks, detect surfaces from a wheelchair, and route around barriers, but nobody has combined many sources, measured how trustworthy each one is using real wheelchair rides, and given an AI that knows when it does not know.** That combination is our opening.

**How to read this:** each topic has a bottom line, a plain-words explanation, a table of 6 to 9 key papers (click the title for the paper), what matters for us, and what is still open. All papers were checked against Crossref, arXiv or the publisher page unless marked otherwise. Figure images could not be fetched for most papers because publisher sites block automated access.

**Three things to discuss with the advisor first:**

1. **Our own group's prior work.** Several closely related papers come from Miami University (Raychoudhury, Gani and co-authors): WheelShare, MyPath, OmniPath and OmniAcc. They must be cited as our baseline.
2. **OmniPath (2026)** already scores OSM paths for slope from aerial LiDAR. Our slope step overlaps; our new part is fusing many sources and validating with wheelchair rides.
3. **MAP (Aug 2026)** is a close competitor to our AI benchmark (RQ4). We differ on harm-weighted scoring, conflicting sources, route questions and small models.

## Topic 1: Mapping sidewalk accessibility

**Bottom line:** crowdsourcing (Project Sidewalk) and open data (OSM, AccessMap) can map sidewalks at city scale, but OSM is very incomplete, and no study has checked OSM against a city's own inventory. Our 4% curb ramp match in Cincinnati fills that gap.

**In simple words:** volunteers look at Google Street View and mark problems (missing ramps, cracks, obstacles). Other projects store sidewalks as map lines with attributes (slope, surface) that a router can use.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Hara, Le & Froehlich, combining crowdsourcing and Google Street View](https://doi.org/10.1145/2470654.2470744) | 2013, CHI | Showed remote crowd workers can find sidewalk problems in Street View; the foundation of Project Sidewalk. |
| [Saha, Froehlich et al., Project Sidewalk](https://doi.org/10.1145/3290605.3300292) | 2019, CHI (best paper) | Washington DC: 797 users, 205,385 labels over 2,941 miles; paid workers found about 68% of problems, about 70% of labels correct. |
| [Duan et al., crowd label quality and cross-city AI](https://doi.org/10.1145/3517428.3550381) | 2022, ASSETS | Tests how crowd label quality affects AI models and whether a model trained in one city works in another. |
| [Bolten & Caspi, personalized pedestrian network analysis](https://doi.org/10.1371/journal.pone.0248399) | 2021, PLOS ONE | AccessMap team: about one third of downtown Seattle is unreachable for a powered wheelchair user. |
| [Bolten & Caspi, community-maintained open sidewalk data](https://doi.org/10.1145/3530190.3534821) | 2022, ACM COMPASS | How communities and agencies can jointly build and maintain sidewalk data with the OpenSidewalks schema. |
| [Omar, Hosseini, Miranda et al., OSM sidewalk completeness](https://arxiv.org/abs/2210.02350) | 2022, arXiv preprint | In 80% of 54 US cities, fewer than 5% of roads have sidewalk tags; kerb, smoothness and width are nearly absent. |
| [Askari, Eisenberg, Froehlich et al., crowdsourced vs official sidewalk data](https://doi.org/10.3390/urbansci9040130) | 2025, Urban Science | Seattle and DuPage County: crowd and city data agree 75 to 100% on whether a feature exists, much less on severity. |
| [Nichols, Groth & Quinn, OSM sidewalks in Maryland](https://doi.org/10.5888/pcd23.260255) | 2026, Preventing Chronic Disease | OSM sidewalks are accurate where mapped but capture only 30% of real sidewalks, 20% in low-density areas. |

&#91;image: Share of roads with sidewalk info in OSM, Chicago, Seattle and NYC, 2008 to 2022\]

*OSM sidewalk coverage grows slowly: even in Seattle, one of the best-mapped US cities, only about 20% of roads had sidewalk info by 2022. Figure from [Omar et al. 2022](https://arxiv.org/abs/2210.02350).*

**Also useful:** [Deitz et al. 2021, "Squeaky wheels"](https://doi.org/10.1177/20539517211047735) found only 17% of 178 US cities publish curb ramp data (Cincinnati does, through CAGIS). [LabelAId, CHI 2024](https://doi.org/10.1145/3613904.3642089) improves crowd label checking by 36.7%. [Mobasheri et al. 2017](https://doi.org/10.1186/s40965-017-0040-5) studies Wheelmap data quality.

**Most relevant to us:**

- Our finding (about 4% of 14,970 city curb ramps appear in OSM) is new evidence for a gap these papers describe but did not measure against a city inventory.
- Nichols 2026 shows low-density towns have the worst coverage. Oxford is exactly that case.

**Still open:** condition and severity, not just presence; small towns; validating OSM itself against city inventories; using 311 as a time-stamped condition signal; fusing all sources with elevation. Not checked yet: whether Project Sidewalk has ever been deployed in Ohio beyond Columbus.

## Topic 2: Finding sidewalks and curb ramps in images

**Bottom line:** computers now find sidewalks and curb ramps in photos well (up to 98% of sidewalks, AP 0.92 for ramps), but they cannot measure slope, cross slope or condition reliably. That is exactly what a wheelchair's own sensors can add.

**In simple words:** two kinds of photos are used: aerial (taken from planes, looking down) and street view (taken from cars, like Google Street View). AI models learn to outline sidewalks or spot ramps in them.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Hara et al., Tohme](https://doi.org/10.1145/2642918.2647403) | 2014, UIST | First curb ramp finder in Street View, mixing computer vision with crowd workers; matched manual accuracy in 13% less time. |
| [Weld et al., Deep learning for automatically detecting sidewalk accessibility problems](https://doi.org/10.1145/3308561.3353798) | 2019, ASSETS (best student paper) | Trained on 300k Project Sidewalk labels; good at checking existing labels (81% precision), weak at finding new problems (47%). |
| [Hou & Ai, sidewalk and curb ramp inventory from mobile LiDAR](https://doi.org/10.1016/j.trc.2020.102772) | 2020, Transportation Research Part C | Builds sidewalk and ramp inventories from laser scans taken by a moving vehicle. |
| [Hosseini et al., CitySurfaces](https://doi.org/10.1016/j.scs.2021.103630) | 2022, Sustainable Cities and Society | Identifies sidewalk paving material from street photos (90.5% mIoU), tested on 6 unseen cities. |
| [Hosseini et al., Tile2Net](https://doi.org/10.1016/j.compenvurbsys.2023.101950) | 2023, Computers, Environment and Urban Systems | Open-source tool turning aerial images into a routable sidewalk network; finds 98% of official sidewalks in Boston and Manhattan; trees hurt it. [code](https://github.com/VIDA-NYU/tile2net) |
| [Liu et al., sidewalk condition benchmark](https://doi.org/10.1145/3663548.3688531) | 2024, ASSETS | First open benchmark for 33 sidewalk condition types; only 13 reach F1 0.7; "steep curb ramp" scored 0. |
| [O'Meara et al., RampNet](https://arxiv.org/abs/2508.09415) | 2025, ICCV workshop | Turns city curb ramp lists into 850k image labels across 3 cities; detector AP 0.92 vs 0.38 for the 2019 model. |
| [Wang et al., Do VLMs see what sensors feel?](https://arxiv.org/abs/2606.07642) | 2026, WACV 2027 (accepted) | Vision-language models rate street scenes against ADA rules, checked against real wheelchair GPS traces at 407 campus spots. |

**Most relevant to us:**

- **RampNet** uses a city ramp inventory as labels, like our CAGIS layer. Our 14,970 Cincinnati ramps could train or test a detector for Oxford, where no inventory exists.
- **Wang et al. 2026** is the only work validating image models with real wheelchair data, on one campus. Our chair sensors could do this at city scale.
- A Sept 2026 preprint ([Lieu et al.](https://arxiv.org/abs/2609.17882)) found vision-language models cannot estimate cross slope precisely enough for ADA checks.

**Still open:** slope and cross slope from images (fails today); condition and severity; small towns where street imagery is old or missing (Oxford); out-of-date official maps (Cambridge's changed 9.2% in 7 years); no Ohio or Midwest study.

&#91;image: RampNet pipeline: city curb ramp coordinates are turned into labels on Street View panoramas\]

*RampNet (O'Meara et al. 2025): a city's list of curb ramp locations (left) is projected onto Street View panoramas to auto-label ramps (right). Our CAGIS ramp list could feed the same pipeline. Figure from [arXiv 2508.09415](https://arxiv.org/abs/2508.09415).*

## Topic 3: Sensing from the wheelchair

**Bottom line:** detecting surfaces and barriers from wheelchair motion sensors is an established field since about 2012. What nobody has done is use wheelchair sensor data to **check how accurate city or OSM maps are**. That part of RQ2 looks open.

**In simple words:** a phone or sensor on the wheelchair feels every bump and tilt. Bumps reveal the surface type; tilt reveals slope; sudden jolts reveal curbs.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Iwasawa, Yairi & Matsuo, wheelchair action sensing for accessibility data](https://doi.org/10.1587/transinf.2015EDP7278) | 2016, IEICE Trans. | Accelerometer on wheelchairs detects curbs, tactile paving and slopes (F1 0.50 to 0.65), replacing manual surveys. |
| [Watanabe et al., wheelchair behavior recognition with deep networks](https://arxiv.org/abs/2101.03724) | 2020, IJCAI-PRICAI workshop | Supervised, weakly supervised and self-supervised surface learning from a phone under the seat. **Closest prior work to SurfaceEncoder.** |
| [Civitarese et al., detecting urban features from wheelchair movements](https://doi.org/10.1109/PERCOM.2019.8767422) | 2019, PerCom | Infers steps and ramps from wheelchair inertial data (about 0.9 precision, 10 users); journal version SmartWheels 2020. |
| [Yu, Raychoudhury et al., surface classification using vibration patterns](https://doi.org/10.1109/TAI.2022.3190828) | 2023, IEEE Trans. AI | Supervised surface classification: 32 surfaces, 32 people, 6 countries, 97.5% accuracy. Miami group. |
| Edinger, Raychoudhury et al., WheelShare: crowd-sensed surface classification for accessible routing | 2019, PerCom Workshops | Vision paper: crowd-sensed vibration feeding an OSM router. Miami group. |
| [Mobasheri et al., enriching OSM with sidewalk geometries](https://doi.org/10.3390/s18020509) | 2018, Sensors | Builds OSM sidewalk lines from wheelchair GPS traces (96% overlap, Heidelberg); geometry only. |
| [Duvall et al., pathway roughness thresholds for wheelchair users](https://pubmed.ncbi.nlm.nih.gov/27588607/) | 2016, Assistive Technology | Links pavement roughness to wheelchair vibration; basis of the ASTM E3028 roughness standard. |
| [Wang, Sun & Liu, self-supervised drivable area segmentation for robotic wheelchairs](https://doi.org/10.1109/LRA.2019.2932874) | 2019, IEEE RA-L | Depth camera on a wheelchair finds drivable area and road hazards; public dataset of 3,896 images. |
| [Hossain, Mahmud, Raychoudhury, Gani, OmniPath](https://arxiv.org/abs/2606.24129) | 2026, COMPSAC | **Scores OSM paths for slope, cross slope and vertical breaks from aerial LiDAR**, checked against 200 field surveys (F1 about 0.6). Miami group; no wheelchair data. |

**Important for us:**

- **The Miami Raychoudhury and Gani group already has a body of work here** (WheelShare, MyPath, Yu 2023, OmniPath, OmniAcc). Check with the advisor how this project relates, and cite these as the group's own prior work.
- **OmniPath overlaps with our slope step.** Our DEM slope pipeline repeats part of it. Our new part must be multi-source fusion plus validation with real wheelchair rides, which OmniPath does not have.
- **SurfaceEncoder** cannot claim to be the first self-supervised wheelchair surface model (Watanabe 2020). Its claim should rest on scale (52M points, 5 countries) and cross-country transfer.
- **mmRAMP:** no public raw radar + depth + IMU wheelchair dataset was found, which supports its novelty; do one more IEEE search for 2023 to 2026 before saying "first".

**Still open:** using chair data to score city or OSM maps (our RQ2); validated running and **cross slope** from a moving wheelchair IMU; a continuous roughness score tied to ASTM E3028; radar-based curb height.

No figures could be fetched (publisher pages blocked automated access).

## Topic 4: Accessible routing and personalization

**Bottom line:** routing tools for wheelchairs exist since 2006, but almost all use preferences the user types in by hand, and none gives a calibrated chance that a segment is a barrier. Handling unknown data is the open problem.

**In simple words:** a normal map finds the shortest route. A wheelchair router adds a "cost" for slope, bad surface or missing ramps, tuned to each person. The hard part is what to do when the map simply does not know.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Beale et al., Mapping for wheelchair users: route navigation in urban spaces](https://doi.org/10.1179/000870406X93517) | 2006, Cartographic Journal | Early GIS route planner (MAGUS) built from wheelchair users' knowledge of local barriers. |
| [Kasemsuppakorn & Karimi, Personalised routing for wheelchair navigation](https://doi.org/10.1080/17489720902837936) | 2009, J. Location Based Services | The standard personal cost function: 6 criteria (width, slope, surface, ...) weighted per user from a 15-question survey. |
| [Kasemsuppakorn et al., Understanding route choices for wheelchair navigation](https://doi.org/10.3109/17483107.2014.898160) | 2015, Disability and Rehabilitation: Assistive Technology | Tested personal routes with 5 manual wheelchair users; 4 of 5 preferred them. |
| [Bolten & Caspi, AccessMap website demonstration](https://doi.org/10.1145/3308561.3354598) | 2019, ASSETS | Deployed open-source sidewalk router (Seattle and others) with user limits on incline and curb ramps; more than 35,000 route requests. |
| [Bolten & Caspi, personalized pedestrian network analysis](https://doi.org/10.1371/journal.pone.0248399) | 2021, PLOS ONE | One network per user profile, plus equity metrics comparing how far each profile can reach across a city. |
| [Kirkham & Tannert, A to B routing simulations](https://doi.org/10.1145/3447526.3472056) | 2021, MobileHCI | 460 million simulated trips: with imperfect data, routers should minimize and show risk, not promise barrier-free routes. |
| [Li et al., Accessibility for Whom?](https://doi.org/10.1145/3706598.3713421) | 2025, CHI | 190 people using 5 mobility aids rated 52 barrier images differently; open dataset and personal routing prototype. |
| [Karki et al., OmniAcc](https://arxiv.org/abs/2509.07220) | 2025, arXiv (AAAI 2025 workshop) | GPT-4 assistant combining satellite images and OSM for personal routing and Q\&A; 97.5% crosswalk detection. |

**Important for us: OmniAcc is very likely our lab's own prior work.** Its authors include Nadim Mahmud, whose account appears in the Accessibility-Assistant repo's history. Treat it as our baseline and cite it as our previous system. A Miami University thesis on an LLM wheelchair assistant (MyPath) also exists but could not be opened; check with the advisor.

Also relevant: [Neis & Zielstra 2014](https://doi.org/10.1016/j.apgeog.2013.09.005) (routing for disabled people from OSM; DOI not checked) and [Anisha & Kirkham 2022](https://doi.org/10.1145/3572921.3572953) (users' attitudes to route risk).

**Still open, and relevant to us:**

- A clear rule for segments with unknown data, with different risk tolerance per user.
- Route explanations that say where each fact came from and how old it is.
- Learning a user's preferences from conversation, checked against the CHI 2025 dataset.
- Field tests with wheelchair users comparing personal and shortest routes.
- Guardrails so an LLM never calls a route accessible when the data does not support it (links to RQ4).

No figures could be fetched (publisher pages blocked automated access).

## Topic 5: Combining noisy sources and choosing what to measure

**Bottom line:** the methods exist and are mature, but no paper applies them to sidewalk or accessibility data. That gap is our RQ2 and RQ3.

**In simple words:** "Truth discovery" means: several sources disagree, nobody knows the truth, so estimate at the same time *what is true* and *how reliable each source is*. A source that usually agrees with the consensus earns more trust.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Dawid & Skene, Maximum likelihood estimation of observer error-rates](https://doi.org/10.2307/2346806) | 1979, Applied Statistics | Learns an error table for each source with no ground truth, treating the true value as hidden. Template for our per-source, per-attribute trust. |
| [Yin, Han & Yu, TruthFinder](https://doi.org/10.1109/TKDE.2007.190745) | 2008, IEEE TKDE | First truth-discovery algorithm: alternately scores source trust and fact confidence. |
| [Raykar et al., Learning from crowds](https://jmlr.org/papers/v11/raykar10a.html) | 2010, JMLR | Learns a predictor, each labeller's reliability and the truth together, so features like slope can sit in the same model. |
| [Li et al., CRH: resolving conflicts in heterogeneous data](https://doi.org/10.1145/2588555.2610509) | 2014, SIGMOD | Handles mixed yes/no and numeric attributes at once; closest ready-made fit for ramp presence plus slope. |
| [Ouyang et al., Truth discovery in crowdsourced detection of spatial events](https://doi.org/10.1145/2661829.2662003) | 2014, CIKM (TKDE 2016) | Models whether a reporter actually visited a place, so "no report" is not read as "no problem". Maps directly onto 311 and OSM gaps. |
| [Zhao et al., A Bayesian approach to discovering truth from conflicting sources](https://doi.org/10.14778/2168651.2168656) | 2012, PVLDB | Separate false-positive and false-negative rates per source; suits OSM, which omits ramps rather than inventing them. |
| [Li et al., A survey on truth discovery](https://doi.org/10.1145/2897350.2897352) | 2016, SIGKDD Explorations | Overview of method families; flags copying between sources as an open problem. |
| [Krause, Singh & Guestrin, Near-optimal sensor placements in Gaussian processes](https://jmlr.org/papers/v9/krause08a.html) | 2008, JMLR | Picks where to measure next by how much it tells you about unmeasured places, with a guarantee. Basis for "which segment to ride next". |
| [Krause & Guestrin, Optimal value of information in graphical models](https://doi.org/10.1613/jair.2737) | 2009, JAIR | Chooses observations by their effect on a downstream decision, such as a route. |

**Useful context:** [Haklay 2010](https://doi.org/10.1068/b35097) is the classic OSM quality study. A 2022 preprint builds a [trust index for OSM sidewalks from edit history](https://arxiv.org/abs/2210.02350), which could serve as a starting trust value for OSM.

**Still open, and relevant to us:**

- Trust that varies by neighbourhood, not one number per source.
- Missing data that is not random: no 311 complaint does not mean the sidewalk is fine.
- Sources that copy each other (OSM imports from city GIS), which breaks the classic models' assumptions.
- Checking whether combined probabilities are calibrated against real wheelchair measurements.
- Choosing audits by their effect on routes, with different audit costs.

No figures could be fetched for these papers (the publisher blocked automated access).

## Topic 6: Fairness of sidewalks, curb ramps and 311

**Bottom line:** no study combines accessibility-specific 311 requests, a curb ramp inventory, disability prevalence and redlining. Nothing exists for Cincinnati. RQ1 looks novel, especially its disability focus.

**In simple words:** 311 data shows who *complains*, not who has problems. Richer areas report more and faster, so a fair analysis must correct for that before comparing neighbourhoods.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Kontokosta & Hong, Bias in smart city governance: 311 complaint behavior](https://doi.org/10.1016/j.scs.2020.102503) | 2021, Sustainable Cities and Society | 311 complaint rates depend on demographics (Kansas City), so 311 volume is a biased measure of need. |
| [Liu, Bhandaram & Garg, Quantifying spatial under-reporting disparities in resident crowdsourcing](https://doi.org/10.1038/s43588-023-00572-6) | 2023, Nature Computational Science | Uses duplicate reports to measure reporting speed without ground truth; some NYC/Chicago areas report about 3x faster, rising with income and % White. |
| [Hamel & Holliday, Unequal responsiveness in city service delivery: 42 million 311 calls](https://doi.org/10.1561/100.00022089) | 2024, Quarterly Journal of Political Science | Across 13 cities, whiter and richer areas get faster responses, mostly because they file different request types. |
| [Clark, Brudney, Jang & Davy](https://doi.org/10.1177/0275074019894564) | 2020, American Review of Public Administration | Across 15 cities, no systematic response-time bias against poor or minority areas; small, city-specific differences. (Check exact title before citing.) |
| de Benedictis-Kessner, Where the Sidewalk Ends | about 2023, Harvard Kennedy School working paper | Closest to RQ1: Boston sidewalks in poorer, minority areas improve more slowly, and uneven 311 use keeps the gap. (Not yet peer-reviewed.) |
| [Rajaee et al., Disparities of sidewalk quality in a rust belt city](https://pmc.ncbi.nlm.nih.gov/articles/PMC8666347/) | 2021, SSM Population Health | Field audit of about 80 miles in Pontiac, MI: worse sidewalks in lower-income, more Black and Latinx areas. |
| [Locke et al., Residential housing segregation and urban tree canopy in 37 US cities](https://doi.org/10.1038/s42949-021-00022-0) | 2021, npj Urban Sustainability | Standard template for linking 1930s redlining grades to today's infrastructure (23% vs 43% tree canopy, D vs A). |
| [Taylor et al., Historical redlining and pedestrian fatalities](https://doi.org/10.2105/AJPH.2022.307192) | 2023, American Journal of Public Health | Redlined (grade D) tracts have 2.6x the pedestrian death rate of grade A; suggests but does not measure infrastructure as the cause. |

**Still open, and relevant to us:**

- Accessibility 311 categories (curb ramps, obstructions, audible signals) have never been studied separately.
- No study joins disability prevalence to curb ramps or 311 outcomes.
- No peer-reviewed study tests redlining against sidewalk or curb ramp condition.
- Cincinnati's 2004 to 2026 series is longer than any 311 panel studied; Rust Belt evidence is thin.

**Methods to borrow:** compare response times within one request type (Hamel & Holliday); use survival models so still-open tickets count correctly; correct for reporting bias (Liu et al.); control for hilliness (an Oakland study found terrain confounds curb ramp patterns); join to redlining polygons by point, not by tract.

No figures could be fetched (publisher pages blocked automated access).

## Topic 7: LLMs, accessibility questions and knowing when to say "I don't know"

**Bottom line:** no benchmark yet scores *which direction* an AI is wrong (false "accessible" vs false "not accessible") together with abstention. The closest work, MAP (Aug 2026, Zurich), must be cited and positioned against.

**In simple words:** today's AI tests mostly count right vs wrong. Few reward "I don't know", and none say that a wrong "yes, it's accessible" is worse than a wrong "no". That is the core of RQ4.

| Paper | Year, venue | Main contribution (one line) |
| --- | --- | --- |
| [Armitage et al., MAP](https://arxiv.org/abs/2608.28384) | 2026, arXiv preprint | **Closest to RQ4.** 4,514 Zurich places, 59 accessibility features, 10 frontier models; labels answers Safe / Unverified / Contradictory / Potentially unsafe. Web search made answers *more* contradictory. |
| [Dihan et al., MapEval](https://arxiv.org/abs/2501.00316) | 2025, ICML | 700 map questions in 180 cities; best model 66%, all trail humans by more than 20 points; routing and distance are hardest. |
| [Wang et al., GeoHaluBench](https://doi.org/10.18653/v1/2025.findings-emnlp.45) | 2025, Findings of EMNLP | Measures made-up facts about places in 13 cities and 20 models; worse for less-known regions. |
| [Panda et al., AccessEval](https://doi.org/10.18653/v1/2025.emnlp-main.1653) | 2025, EMNLP | 21 models, 9 disability types: disability-related questions get more factual errors and more refusals. |
| [Kirichenko et al., AbstentionBench](https://arxiv.org/abs/2506.09038) | 2025, NeurIPS | 35k questions from 20 datasets; reasoning-tuned models abstain about 24% less when they should; bigger models barely help. |
| [Wen et al., Know Your Limits: survey of abstention](https://doi.org/10.1162/tacl_a_00754) | 2025, TACL | Standard map of abstention methods, benchmarks and metrics. |
| [Wang et al., RAG with conflicting evidence (RAMDocs)](https://arxiv.org/abs/2504.13079) | 2025, arXiv | Benchmark for retrieved documents that disagree; best baseline only 32.6% exact match. |
| [Kalai et al., Why language models hallucinate](https://arxiv.org/abs/2509.04664) | 2025, arXiv | Shows benchmarks reward guessing; proposes +1 right, 0 for "I don't know", a penalty for wrong. Direct template for our harm metric. |

&#91;image: MAP benchmark: claim verification and visual evidence retrieval tasks for accessibility in Zurich\]

*MAP (Armitage et al. 2026), the closest work to RQ4: models answer accessibility questions about Zurich places and are scored as safe or unsafe. Figure from [arXiv 2608.28384](https://arxiv.org/abs/2608.28384).*

**How RQ4 differs from MAP:**

|  | MAP | Our plan |
| --- | --- | --- |
| Region | Zurich | Cincinnati + Oxford, Ohio |
| Error cost | safety labels, no numeric weights | numeric weights: false "accessible" costs more |
| Conflicting sources | resolved or removed from the test | tested on purpose |
| Route and slope questions | excluded | included |
| Small on-device models | not tested | compared with frontier and RAG |

Also relevant: [Whitehead et al. 2022](https://arxiv.org/abs/2204.13631) ("effective reliability" metric with a cost for wrong answers), [Kadavath et al. 2022](https://arxiv.org/abs/2207.05221) (models can partly estimate their own correctness), [Wheelpedia, ASSETS 2024](https://doi.org/10.1145/3663548.3675609) (LLM chatbot for wheelchair users, no error test). One PDF-audit study ([arXiv 2509.18965](https://arxiv.org/abs/2509.18965)) found a model invented answers in 32% of "cannot tell" cases and leaned toward "compliant": the exact failure our metric targets.

**Still open:** direction-weighted errors plus abstention; route and slope questions; conflicting accessibility sources; small vs frontier models on abstention; any US or Ohio coverage.

## Gap map: what is done, what is open

Every research question has an open gap, but each must be positioned against one or two close papers.

| Our question | Already done by others | Still open (our chance) | Closest work to cite | Novelty |
| --- | --- | --- | --- | --- |
| RQ1 fairness of ramps and 311 | 311 reporting bias; sidewalk quality by race and income; redlining vs tree canopy and pedestrian deaths | Accessibility-specific 311 types; disability prevalence; redlining vs curb ramps; Cincinnati 2004 to 2026 | Liu et al. 2023; Hamel & Holliday 2024; de Benedictis-Kessner | High |
| RQ2 which source to trust | Wheelchair sensors classify surfaces and barriers; crowd vs city data compared on presence | Using chair data to score OSM and city maps; cross slope from a moving chair | Askari et al. 2025; OmniPath 2026; Yu et al. 2023 | High |
| RQ3 uncertainty map and next audits | Truth discovery and sensor-placement methods exist; routers minimize risk | Applying them to sidewalks; learned per-source trust; choosing audits by route impact | Dawid & Skene; Ouyang et al. 2014; Krause et al. 2008; Kirkham & Tannert 2021 | High |
| RQ4 AI that knows when it doesn't know | Place accessibility benchmark (Zurich); abstention benchmarks; scoring that rewards "I don't know" | Direction-weighted harm; conflicting sources; route and slope questions; small models; US data | MAP 2026; AbstentionBench 2025; Kalai et al. 2025 | Medium (must beat MAP clearly) |
| Slope from height maps (data step) | OmniPath scores OSM slope from LiDAR | Not new on its own; useful as one input to RQ2 and RQ3 | OmniPath 2026 | Low alone |
