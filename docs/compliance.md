# Compliance: crawler rules, privacy and what is still open

Written 2026-11-16 for review by the team before deployment. This is a working policy by the developers, **not legal advice**; the open items at the end need the lab, the library or counsel.

## 1. What the crawler does and does not do

| Rule | How it is enforced | Where |
|---|---|---|
| Obey robots.txt on every request | Scrapy setting `ROBOTSTXT_OBEY`; our agent name is `accessibility-map` | `crawler/run.py` |
| Be slow and gentle | delay between requests to one site, `Crawl-delay` and `Retry-After` honoured, back off on 429/503, stop on repeated failures, conditional GET (304) so unchanged pages are not downloaded again | `crawler/spider.py` |
| Public pages only | no logins, no CAPTCHAs, no evading blocks; paths like login, cart, search and delete are skipped | `crawler/urls.py` trap guard |
| Never touch private networks | private and internal addresses are blocked unless a test asks for them | `crawler/run.py` |
| **Respect terms of use** | each site's usual terms pages are fetched first; if one forbids robots, scraping or automated access, the crawl of that site stops, nothing it sent is kept, and the site is listed under `tos_restricted` in `data/crawl/<source>/report.json`. A person then asks for permission. After permission, add the host to the spec's `tos_allow`. Known-bad sites can be listed in `tos_restricted` | `crawler/tos.py` |
| Small footprint | per-site page budgets (8 to 10 pages for small sites), a site with nothing relevant is dropped after five pages | `crawler/seeds.py`, `spider.py` |

Limits of the terms check: it finds only terms pages at the usual addresses (`/terms`, `/terms-of-use`, `/terms-of-service`, `/terms-and-conditions`, `/legal`) and reads English wording. A site with its terms elsewhere, or in a PDF, is not caught. Treat it as a safety net; for any site that matters, read the terms once by hand.

## 2. Personal data

| Data | What we do |
|---|---|
| Email addresses on crawled pages | personal-looking ones (`name@...`) are replaced by `[email removed]` before storage; role addresses such as `info@` or `accessibility@` are kept because they are public contact points |
| Phone numbers | numbers marked cell, mobile, home or personal are removed; business and office numbers are kept (they are facts about a place) |
| Raw page files | stay on the researcher's computer (`data/crawl`, git-ignored), are not published; only the cleaned documents and short quoted facts with links are intended for release |
| Report form (text, optional photo, optional email or phone) | stored in the project's own Supabase table that browsers cannot read; only the accessibility team reads it. Photos are shrunk and lose camera and location data in the browser; the form asks people not to write names or show faces and number plates. No name, no IP address stored |
| Privacy note and deletion | the form has a "How we use your report" note (purpose, who reads it, kept up to 24 months, never published). Right after sending, a person can press "Delete this report". Reports older than 24 months are removed by `purge_old_reports()` (run it now and then, or schedule it) |
| Questions people ask the assistant | not collected in this version |

After changing the SQL, re-run `supabase/problem_reports.sql` in the Supabase SQL editor (it is safe to run again) to add the delete and purge functions.

## 3. Using the data

- Release **facts and short quotes with links back**, not copies of pages. Government open data and OpenStreetMap/Overture follow their own licences (kept on each dataset card, `data/cards/`).
- Every fact carries its source, date and a rating, so an owner who objects can be found and the fact removed.
- A site owner who writes to us gets: removal of their pages from the data and a block on future crawls of the site.
- Reddit: only through approved research API access, never by scraping.

## 4. Still open (needs people)

1. **Crawler contact.** The User-Agent has no contact URL or email yet. Create a role address (not a personal one) and a short "about this crawler" page (what it is, what it collects, how to opt out) and put its address into `USER_AGENT` in `src/atlas/core.py`. This is the most important fix.
2. **Counsel or library review** of releasing data derived from web pages, and whether Miami needs an IRB or compliance review for the report form's photos and contact details.
3. **Retention rule.** 24 months is my proposal; the lab should confirm it.
4. **Sites crawled before the terms check existed** (the 80 Oxford place pages, the DC and Dayton government sites) were crawled under robots.txt only. Government sites and public-agency pages are low risk; for the businesses, read the terms of any site whose facts we plan to publish.
5. **A named person** who answers site-owner complaints and decides on removals.
