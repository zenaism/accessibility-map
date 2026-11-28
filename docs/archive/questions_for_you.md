> **Archived 2026-11-27.** Historical record: this was built, answered or superseded. Current docs: [`../README.md`](../README.md), [`../decisions.md`](../decisions.md), [`../ui_handout.md`](../ui_handout.md).

# Questions for you (answered 2026-11-15; applied in decision D-21)

All open questions from the plans, in one place and without duplicates. Write your answer on the **Answer:** line (a few words is enough; "your call" means I use my recommendation). Tell me when it is filled and I will apply it to the plans and the decision log. Where I have a recommendation it is marked **Recommend**.

Sources of the questions: `crawler_plan.md` section 13, `national_data_plan.md` section 9, `system_overview.md` section 10, `data_needs.md` section 6.

## A. Scope and people

**A1. Which places, and by when?** Is "Maryland" the whole state or some counties (for example Montgomery, Prince George's, Baltimore)? Which other cities did your professor name, and what is the deadline for Maryland and DC?
Recommend: start with Washington DC, then two or three Maryland counties, then Dayton.
Answer: we should be able to get the data about the whole city, for example washington DC

**A2. Which two or three predictions matter most** for your papers and for the other team's app (missing attributes, repair risk, outages, source reliability, personal routes)? This decides which labels we collect first.
Answer:outages,  personal routes ... rest u decide

**A3. The other team:** which data format do they want (Parquet, GeoJSON, DuckDB or SQLite file, a web API), how often do they need updates, and which attributes matter most to their app?
Recommend: versioned Parquet files plus a DuckDB file, monthly updates.
Answer: files should be accaptable for them 

## B. Resources (budget is $0)

**B1. Compute:** is there a lab or university GPU, or must everything run on the laptop? (Decides how much OCR and vision work is realistic.)
Answer:  for now we have to run it on my computer. 

**B2. Storage:** where can large raw archives live for free (lab server, university storage, Zenodo, Hugging Face)? Do you want WARC files for sharing and replay?
Answer:maybe zenodo will work. 

**B3. Raw history:** how much raw history do we keep (hourly transit alerts, page snapshots), given storage limits?
Recommend: keep everything for the two target regions; thin old snapshots later.
Answer: let's do what u recommended 

**B4. Crawler contact:** who is the contact for the crawler's identity page (so sites can reach us), and can the lab host that page?
Answer: not sure yet. 

## C. Crawler decisions

**C1. Approach:** Scrapy first with a custom fallback after a 2 to 3 day spike (my plan), or build the whole crawler ourselves?
Recommend: Scrapy first.
Answer: use your recommendation 

**C2. Rules:** may the crawler rely on robots.txt only for public venue pages, and what is the lab's rule for sites whose terms forbid automated access (skip, or ask permission)?
Recommend: robots.txt, no logins, skip and ask permission when the terms forbid bots.
Answer:

**C3. What to save:** images and documents from every in-scope page (more storage, more future value) or only from relevant pages?
Recommend: relevant pages only at first; all pages later if storage allows.
Answer:  use the recommendation

## D. Data rules

**D1. Rating cut-offs:** are tiers A 80, B 50, C 30 and the starting weights acceptable, or stricter?
Answer: sounds good. 

**D2. Calibration set:** build a one-time set of about 100 labelled facts from official data to tune the weights?
Recommend: yes.
Answer: use recommendation 

**D3. Licensing stance:** release only data with clearly open licences, or also fact-level extractions from websites (short quotes with links back)?
Recommend: facts and short quotes with links; keep full page copies private.
Answer: use recommendation 

**D4. Reddit and reviews:** keep Reddit in scope (needs approval, strict terms)?
Recommend: not in the first release.
Answer:I want data from reddit 

**D5. Street imagery:** is Mapillary in scope, or only documents, posters and maps?
Recommend: documents, posters and maps first.
Answer: what is it? if posisbel use it Mapillary

## E. Research and ethics

**E1. Lab data:** can the wheelchair recordings (mmRAMP, SurfaceEncoder) be joined to our map by location and time?
Answer: 

**E2. User data:** collect any opt-in user profile or feedback in version 1, or only after ethics (IRB) review?
Recommend: only after IRB review.
Answer:

**E3. Redistribution advice:** will you ask the Miami library or counsel about redistributing data derived from web pages before the first release?
Answer:

## What I did with your answers (2026-11-15)

- **Applied** in `decisions.md` D-21 and in the open-question sections of the plans.
- **Reddit** is now in scope (priority P1 in `config/categories.yaml`). It needs research API credentials that only you can request; see the next steps in `progress_log.md`.
- **Mapillary** is in scope if possible: a free street-photo service with an API and some automatic detections; photos are CC BY-SA, so a licence review comes first. It needs a free access token that you create.
- **Blank answers:** C2 (default: skip and ask permission when terms forbid bots), E1 (ask your professor), E2 (default: only after IRB), E3 (still open), B4 (still open).
