# Docs

One topic per file. Where two files touch the same subject, the "owner" below is the single place to edit.

| File | What it is | Owner of |
|---|---|---|
| [`research_questions.md`](research_questions.md) | The four (revised) research questions, papers, venues, plan | RQs, paper plan, timeline |
| [`study_design.md`](study_design.md) | Method and threats to validity | how we test the RQs |
| [`literature/`](literature/) | `literature_review.md` is the short synthesis with the gap map; `topic1` to `topic7` are the detailed notes behind it | related work |
| [`national_data_plan.md`](national_data_plan.md) | Plan for automated, nationwide collection (draft) | discovery, fetching, storage, release format |
| [`data_design.md`](data_design.md) | Cincinnati/Oxford scope, categories, record shapes, pipeline, map | the current data model |
| [`categories.md`](categories.md) | Generated list of all question categories (trails, parking, restrooms, events, ...) with how to fetch each; source is `../config/categories.yaml` | what users ask about, drives fetching |
| [`data_dictionary.md`](data_dictionary.md) | Generated: every column of the observation table (schema v2), the dataset card, candidate table and raw manifest | exact data formats |
| [`crawler_plan.md`](crawler_plan.md) | Research and implementation plan for the web crawler (requirements, tool comparison, architecture, tests, phases) | how we fetch websites |
| [`data_needs.md`](data_needs.md) | All data we need: now, for computing, for prediction; what to keep from day one | data requirements and future use |
| [`data_landscape.md`](data_landscape.md) | What users need and every way to get it, by acquisition method | acquisition strategy |
| [`source_catalog.md`](source_catalog.md) | Researched candidate sources: what each adds, access, terms, priority | source reasoning |
| [`source_inventory.md`](source_inventory.md) | **Source tracker, updates itself after every `atlas fetch`**: URL, licence, counts, last retrieved, failures. Do not edit | what is on disk |
| [`resource_directory.md`](resource_directory.md) | Annotated list of local accessibility organisations and platforms | people and organisations |
| [`assistant_design.md`](assistant_design.md) | Tool-using assistant design and the 44-question bank | assistant, evaluation questions |
| [`system_overview.md`](system_overview.md) | **Start here.** How the system works, automatic rating, pros and cons, comparison with other architectures, status | the overview |
| [`architecture.md`](architecture.md) | Mermaid diagrams: system, discovery, crawl and completeness checks, extraction, data model, storage, assistant | how the system fits together |
| [`source_types.md`](source_types.md) | Non-government source types, licences, region findings (DC, MD, Dayton) | which kinds of sources we need |
| [`questions_for_you.md`](questions_for_you.md) | **Your answer sheet:** every open question in one place, with my recommendations | what I need from you |
| [`problem_reports.md`](problem_reports.md) | "Report a problem" with photo: how it works, privacy, turning it on, how the accessibility team reads reports | visitor problem reports |
| [`decisions.md`](decisions.md) | Decision log: what we chose, why, alternatives, costs | the reasoning behind choices |
| [`progress_log.md`](progress_log.md) | Dated progress, findings, collection status, to-do (snapshot of the Claude Doc) | what has been done |
| [`outreach_emails.md`](outreach_emails.md) | Draft emails to data owners (not sent) | outreach |
| `*.docx`, `figures/` | Research brief, RQ system notes, images | |

Source *status* (collected, next, ideas) is in [`../SOURCES.md`](../SOURCES.md).

## Overlaps (resolved by pointing to one owner)
- `data_landscape.md` (user needs by acquisition method), `national_data_plan.md` section 2 (question families) and `assistant_design.md` (question bank) describe the same user needs from three angles; they should share one attribute list.
- `source_catalog.md`, `resource_directory.md` and `../SOURCES.md` list many of the same sources (catalog = reasoning, SOURCES = status, directory = descriptions).
- `data_design.md` (record shapes) and `national_data_plan.md` (observation schema v2) both define the schema; v2 should replace the record shapes once approved.
