# Problem reports: how it works, how to turn it on, how the accessibility team uses it

Visitors can press **Report a problem** on any place (in the map popup and in the place details) or on the map as a whole
(bottom of the list). They pick what kind of problem it is, write what happened, and can add a photo from the device or
take one with the camera. Reports are stored in our Supabase database and the accessibility team reads them there.

> **Update (branch `ui/report`, 2026-11-24):** on the new map page the "Report a problem" dialog described below is replaced by
> the one-screen **Rate or report** form (stars 1 to 5, problem chips Blocked, Broken lift, Wrong info, Other, optional comment
> and photo, one Send button). It uses the same database functions; nothing in the SQL changed. A problem needs no typed text:
> the chip name is sent when the comment is empty. Photos go only with a problem. The privacy line is "No name needed. We keep
> your report, device type and page address." and the What we keep sheet lists what is stored. See `docs/ui_components.md`,
> D-77 to D-81 in `docs/decisions.md` and `tests/test_report_form.py`. The text below describes the legacy dialog.

## For visitors (what they see)
1. Tap **Report a problem**. A form opens (a bottom sheet on a phone).
2. Choose one of five kinds: *Something is blocked or broken · The information here is wrong · It is harder to use than
   shown · Something is missing · Something else*.
3. Write a sentence or two. A photo is optional (**Take a photo** on phones, **Choose a photo** everywhere). Contact details
   are optional and only for follow-up questions.
4. **Send report.** They get a reference code (for example `1A2B3C4D`). If sending fails, their text and photo stay in the
   form; closing the form by accident keeps the text for next time.

Accessibility of the form itself: it is a native dialog (keyboard focus stays inside, Escape closes it, screen readers
announce it), every field has a real label and hint, errors are listed in words at the top and next to the field, all
buttons are at least 44 px tall, text is 16 px, and nothing relies on colour alone. It was tested in a real browser with
keyboard, a phone-sized screen and error cases (`tests/test_report_ui.py`).

## Privacy
- No name, account or IP address is stored. A random device id (kept in the visitor's browser) is used only to limit abuse
  (10 reports per device per day).
- The photo is shrunk and re-encoded **in the browser before it is sent**, which removes camera data and GPS position.
  The form tells people to avoid faces and number plates. Photos are stored as small JPEGs (at most 400 KB).
- The optional contact field is shown only to the team. Reports are not shown publicly.
- Suggested retention: review reports monthly and delete closed ones with photos after 12 months (decide with the team).

## Turning it on (one time, about 3 minutes, needs the project owner)
1. Open the Supabase project -> **SQL Editor** -> **New query**.
2. Paste the whole of `supabase/problem_reports.sql` and press **Run**. It is safe to run again.
3. Done. The map pages check the database when they load and show the button only when the script has been run, so
   nothing else needs to change and nobody sees a form that cannot save. (Pages are cached by browsers for a short time.)

## For the accessibility team (reading and handling reports)
- **In the dashboard:** Supabase -> **Table Editor** -> the view `problem_reports_review` (newest first; `ref`, status,
  kind, place, description, contact, whether there is a photo). To work a report, open the table `problem_reports`, find the
  row (match the `ref`: the first 8 characters of its `id`), and edit **status** (`new`, `in_review`, `needs_info`, `fixed`,
  `wont_fix`, `duplicate`) and **team_notes**.
- **With photos:** run the export (the project owner has the secret key; keep it out of files and out of git):
  ```
  export SUPABASE_SERVICE_KEY='...secret key from Project settings -> API...'
  python scripts/export_reports.py            # add --status new to export only new reports
  open data/private/reports/index.html
  ```
  It writes `reports.csv`, a `photos/` folder named by reference code, and a plain `index.html` gallery. The folder is under
  `data/private/`, which git ignores, because it holds personal data.
- **What the categories mean:** *blocked or broken* = something that stops use right now (act first); *wrong information* =
  the map disagrees with reality (fix the data); *harder to use than shown* = the rating is too generous; *missing* = a
  place or detail is not listed; *something else*.

## What can go wrong and what we did about it
| Risk | Protection |
|---|---|
| Spam or bots | a hidden field robots fill in (the database silently drops those), 10 reports per device per day, length limits, JPEG-only photos up to 400 KB |
| A failed send loses the report | the text and photo stay in the form; each report has its own id, so a retry cannot store it twice |
| Strangers reading reports or photos | the table and view are locked (row-level security, no grants); only the two functions are open to the public key |
| The form shown before the database is ready | the button appears only after `report_ping()` answers |
| Photo shows where someone lives | re-encoding in the browser strips location data; the text tells people to avoid faces and number plates |

## Limits to know
- The database script was checked by a Postgres parser and by tests that its rules match the form, but **it has not been run
  against the real Supabase project**: please run it and send one test report from a phone, then look at it in the dashboard.
- Photos are stored inside the database rows (simple and reliable with the public key). At about 100 to 300 KB each, a free
  500 MB database holds a few thousand photos; if reports grow beyond that, move photos to Supabase Storage.
- Reports are not moderated or published; the team decides what to do with them.
