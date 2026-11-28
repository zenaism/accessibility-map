> **Archived 2026-11-27.** Historical record: this was built, answered or superseded. Current docs: [`../README.md`](../README.md), [`../decisions.md`](../decisions.md), [`../ui_handout.md`](../ui_handout.md).

# Session prompts, round 2: visual design and the design board

Round 1 produced wireframes (plain black and white on purpose). Round 2 locks the recommended structure, adds a modern look, icons and short text, and ends in one design board where you choose what you like. Copy one block at a time into a separate Claude session.

The board is a free HTML page, not a Figma file. It works the same way (frames per screen, variants side by side, a choose button on each) and it exports your choices as text for the build sessions.

## Order and parallel runs

| Step | Prompt | Run | Notes |
|---|---|---|---|
| 1 | V0 Lock recommendations | now, alone, short | Records the recommended options from 2A, 2B, 2C as chosen |
| 1 | V1 Style directions | now, in parallel with V0 | Writes only to docs/design/style/ |
| 2 | You pick one style direction | | Open docs/design/style/index.html |
| 3 | V2A Map, details, favourites / V2B Report a problem / V2C Chat, voice, settings | after step 2, all three in parallel | Each writes only to its own folder |
| 4 | V3 Assemble the design board | after V2A, V2B, V2C | |
| 5 | You choose options on the board and export your choices | | |
| 6 | B0 Foundation build (tokens, icons, shared components) | after step 5 and the branch work | Alone, first build |
| 7 | B1 Map build, B2 Report build, B3 Chat build | after B0, in parallel in separate worktrees | Favourites is part of B1 |
| 8 | Final review (Prompt 5 in session_prompts.md, updated below) | last, alone | |

---

## Prompt V0: Lock the recommended options

PROMPT START
```text
Short session for the Accessibility Map. I accept the recommendations from the three prototype sessions. Record them as chosen so later sessions can rely on them. Do not change any prototype file.

Read: docs/prototypes/map/README.md and index.html, docs/prototypes/favourites/README.md and index.html, docs/prototypes/chat/README.md and index.html, docs/ux_brief.md, docs/decisions.md.

1. For every part (2A.1 live location and heading, 2A.2 search-first map, 2A.3 details panel, 2B favourites, 2C.1 settings icon, 2C.2 concise answers, 2C.3 chat layout, 2C.4 voice), take the option each README recommends. Where a recommendation depends on an open question, take its stated default. List any part where the README gives no clear recommendation and ask me about it before continuing.
2. Write docs/prototypes/CHOSEN.md: one table with part, chosen option (file name), one-line reason, and the changes the README says to make. Add a short "what this means for the visual design" list (for example which components appear on which screen).
3. Record each choice with its why in docs/decisions.md as new decisions, and mark the earlier "proposed" prototype decisions as accepted. Update the "Progress and to-do" section and docs/progress_log.md.
4. Follow the accessibility-map skill and my memory notes. Commit only the files you changed as zenaism@miamioh.edu, run the gitleaks hook, do not push. My working tree has unrelated modified files; do not stage them.
```
PROMPT END

---

## Prompt V1: Style directions (look and feel)

PROMPT START
```text
Session V1 for the Accessibility Map: choose a modern visual style. Produce a style board for my review. Do NOT touch src/, the live pages or data. Write only inside docs/design/style/.

Context: the prototypes so far are plain black and white wireframes. The system is used by lab students to report problems and by people looking for step-free places, mostly on phones. I want it to look nice, modern and friendly, and be intuitive. Texts must be short. The repo's earlier "minimal accessible style" is no longer the target look, but the accessibility rules stay.

Read first: the accessibility-map skill, docs/ux_brief.md (principles, accessibility checklist, constraints), docs/prototypes/CHOSEN.md if it exists (otherwise the README of each prototype folder), the current live pages and screenshots in docs/figures/ux_audit/, and the artifact-design skill for general visual guidance.

Research (web search, cite links, mark verified or assumed): current mobile map and civic app design patterns (for example bottom sheets, floating search, pill chips, rounded cards, status badges), how modern apps show confidence and "unknown" without clutter, free open-licensed icon sets (for example Lucide, Phosphor, Tabler) and free fonts (SIL OFL) that can be self-hosted. Everything must be self-hosted: no third-party requests at run time (privacy rule in the brief).

Produce three distinct style directions, each shown on the same sample screens so I can compare:
- Tokens: colour palette in light mode and dark mode (primary, surface, text, border, focus ring), the four access-rating colours (yes, partial, no, unknown) that stay readable for colour-blind users and always come with an icon and a word, type (family, sizes, weights), spacing, corner radius, shadow, motion (with a reduced-motion version).
- Icons: one set, with the exact icons for these actions: Ask (chat), Near me (locate), Search, Save/favourite, Route here, Report a problem, Settings, Voice (mic), Stop, Send, More details, Close, Back, Share/copy link, Camera/photo, Filter. Inline SVG. Primary buttons have an icon and a text label; icon-only buttons have an accessible name and a tooltip.
- Components sheet: buttons (primary, secondary, ghost, icon+label, icon-only, disabled, loading), chips, search field, text field, select, toggle, card, place card, rating badge, bottom sheet, top banner, toast, empty state, error state, tab bar or navigation, map pins and cluster, user-location dot with heading cone, chat bubbles, voice button states.
- Two sample screens per direction at 375 px and 1280 px: the map with a search and a place card, and the report-a-problem form.
- A content style guide for short text: sentence case, a word limit per button, per title and per message, plain words, and 10 before-and-after rewrites using real strings from the current UI.
- A measured contrast table for every text and control colour pair (text 4.5:1, control borders and icons 3:1), computed by a script, not estimated. All touch targets at least 44 px.

Deliver docs/style/index.html as docs/design/style/index.html: a page with the three directions side by side (tabs or a switcher), standalone, works offline, works at 375 px and desktop, no external requests. Add docs/design/style/README.md with a short comparison table, your recommendation with reasons, and the questions I must decide. Put reusable tokens for each direction in separate CSS files so a later build can reuse them.

Rules: free tools only, no paid APIs. Follow the skill and memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu (do not stage my unrelated modified files), run the gitleaks hook, do not push. Do not build into the real app. Wait for my choice.
```
PROMPT END

---

## Prompt V2A: Styled screens, map, place details, favourites

PROMPT START
```text
Session V2A for the Accessibility Map: styled design screens for the map area. Produce design frames for my review. Do NOT touch src/, the live pages or data. Write only inside docs/design/map/.

Read first: the accessibility-map skill, docs/ux_brief.md, docs/prototypes/CHOSEN.md (the structure is decided; keep it), the chosen option files it lists in docs/prototypes/map/ and docs/prototypes/favourites/, and my chosen style direction: [DIRECTION NAME AND FOLDER, for example "B, docs/design/style/"] with its token CSS and icon set. Use that style exactly; do not invent new colours or icons.

Design these screens and components, each as a frame at 375 px and, where it makes sense, 1280 px:
- Map, empty start (search-first), with the search field, "Near me" and "Ask" buttons with icons, and a clear prompt.
- Search: typing with suggestions, results on the map and as a list, no results.
- Place card (first layer) and the full details view, including the rating badge, key facts with icons, source and age, and the "Route here" and "Save" buttons. Unknown values.
- Live navigation: follow-me dot with heading cone and accuracy ring, next step banner, locating, poor accuracy, permission denied, no compass, iOS compass permission button, stop following.
- Favourites page: list, empty, many, restore link, warning before storage can be cleared, place removed.
- Header and navigation, and the legend.
Give the 2 most important components (place card and next-step banner) three visual variants each so I can choose; everything else gets one best design. Text is short: follow the content style guide.

Deliver: one standalone HTML file per frame or small group (frames/*.html), a frames.json manifest listing each frame (id, title, group, file, size, variant label, notes) that the board assembly session will read, and a README with an accessibility self-check against the brief (measured contrast, 44 px targets, focus order, screen reader names, reduced motion). Frames work offline, with fake data and no external requests.

Rules: free tools only. Follow the skill and memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu, run the gitleaks hook, do not push. Do not build into the real app.
```
PROMPT END

---

## Prompt V2B: Styled screens, report a problem (lab students)

PROMPT START
```text
Session V2B for the Accessibility Map: styled design screens for reporting problems. Produce design frames for my review. Do NOT touch src/, the live pages, supabase/ or data. Write only inside docs/design/report/.

Context: lab students will use this to report problems (for example a blocked ramp, a broken lift, wrong information about a place) often on their phones, outdoors, quickly, with one hand. It must feel quick, friendly and trustworthy, with very few words.

Read first: the accessibility-map skill, docs/ux_brief.md, docs/problem_reports.md, the current report form (code on branch deploy/routing-pages, worktree accessibility-map-integration; read it, do not edit it, and look at its screenshots), docs/compliance.md (privacy: what is stored and shown), and my chosen style direction: [DIRECTION NAME AND FOLDER] with its token CSS and icon set. Use that style exactly.

Design these screens and components, each at 375 px and, where it makes sense, 1280 px:
- The entry point (the Report button on the map and on a place card) and how it prefills the place.
- The report form as a short flow: what is the problem (large icon choices with 2-word labels), where (place or pin, with Near me), a short description (optional), photo (camera or gallery, small preview, size limit explained in one line), and send. Aim for the fewest taps; show a progress cue if it has more than one step.
- Validation and error states tied to fields (screen reader friendly), offline and retry, photo too large, sending, duplicate, rate limit reached.
- Success screen with what happens next, a way to see or delete the report just sent, and a way to report another.
- A "my reports on this device" list, if the current system supports it (check the code and say so if not).
- The honest privacy note: what is stored (check the code: user agent, page address) in one plain line. Fix the "Anonymous" wording problem noted in docs/improvement_plan.md 3.6.
Give the form's main step and the success screen three visual variants each so I can choose; everything else one best design. Text is short: follow the content style guide.

Deliver: standalone HTML frames in frames/, a frames.json manifest (id, title, group, file, size, variant label, notes), and a README with an accessibility self-check (measured contrast, 44 px targets, focus order, errors tied to fields, reduced motion). Frames work offline with fake data and no external requests.

Rules: free tools only. Follow the skill and memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu, run the gitleaks hook, do not push. Do not build into the real app.
```
PROMPT END

---

## Prompt V2C: Styled screens, chat, voice, settings

PROMPT START
```text
Session V2C for the Accessibility Map: styled design screens for the chat assistant. Produce design frames for my review. Do NOT touch src/, the live pages or data. Write only inside docs/design/chat/.

Read first: the accessibility-map skill, docs/ux_brief.md, docs/prototypes/CHOSEN.md (the structure is decided; keep it), the chosen option files it lists in docs/prototypes/chat/, docs/assistant_design.md, and my chosen style direction: [DIRECTION NAME AND FOLDER] with its token CSS and icon set. Use that style exactly.

Design these screens and components, each at 375 px and, where it makes sense, 1280 px:
- Chat opened from the "Ask" button (with its icon), the greeting, and suggested questions as chips.
- A short answer (one sentence plus one place card) and the expanded "More" state, a follow-up chip row, sources and unknown values, and an error.
- Compose area that always sits above the bottom edge (dvh, safe area, keyboard open), landscape, and 200 percent zoom.
- Voice: idle, recording with a visible counter, restarting, editable transcript, processing, mic denied, limit reached.
- Settings with the proper gear icon and a text label, and its contents as they exist today.
- Typing and loading, offline, and empty history.
Give the short answer with place card and the compose area three visual variants each so I can choose; everything else one best design. Text is short: follow the content style guide.

Deliver: standalone HTML frames in frames/, a frames.json manifest (id, title, group, file, size, variant label, notes), and a README with an accessibility self-check (measured contrast, 44 px targets, focus order, screen reader names, live region for new messages, reduced motion). Frames work offline with fake data and no external requests.

Rules: free tools only, local models allowed. Follow the skill and memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu, run the gitleaks hook, do not push. Do not build into the real app.
```
PROMPT END

---

## Prompt V3: Assemble the design board

PROMPT START
```text
Session V3 for the Accessibility Map: assemble the design board, a free Figma-like page where I look at every screen and component and choose what I like. Do NOT touch src/ or the live pages. Write only inside docs/design/board/ (plus a link line in docs/README.md).

Read first: the accessibility-map skill, docs/ux_brief.md, docs/design/style/README.md and the chosen style files, and the frames.json manifests and frames in docs/design/map/, docs/design/report/ and docs/design/chat/. Use the chosen style for the board's own look.

Build docs/design/board/index.html, a standalone page that works offline with no external requests, with these features:
- A canvas of frames grouped by area (Map, Report, Chat) and by screen, with phone-sized and desktop-sized frames shown in their real size. Frames load the existing frame files (iframes or inline), so frames are not copied or redrawn by hand.
- Navigation: a left list of screens that scrolls the canvas to a frame, zoom in, out and fit, pan by dragging, and a way to open one frame full size. All of it works with the keyboard.
- Variants shown side by side with their labels. On every variant a clear "Choose" control (a radio per screen), and a comment field under each screen.
- A "My choices" panel that lists each screen, the variant I picked, my comments, and what is still undecided, with a progress count. Choices are saved in this browser (localStorage, wrapped in try and catch) and survive a reload.
- Export: "Copy as Markdown" and "Download JSON" of my choices, in a format a build session can read, saved by me into docs/design/CHOSEN_DESIGN.md.
- A toggle for light and dark mode, and a toggle that shows a frame's notes and measured contrast.
- It must itself pass the accessibility checklist in the brief (contrast, keyboard, names, focus, 44 px targets, reduced motion).

Check: every frame in every frames.json appears on the board; none is missing or duplicated. Take screenshots of the board at 1280 px and a narrow window and put them in docs/design/board/. Add a README that says how to open the board, how to choose and export, and how to add a frame later. Also say honestly that this is not a Figma file and what would be needed to move the frames into Figma (do not do it).

Rules: free tools only. Follow the skill and memory notes: record decisions in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu, run the gitleaks hook, do not push.
```
PROMPT END

---

## Prompt B0: Build the foundation (tokens, icons, shared components)

Run after you have exported your choices into docs/design/CHOSEN_DESIGN.md and the branch work is done. Fill in the brackets.

PROMPT START
```text
Build session B0 for the Accessibility Map: the visual foundation that the later builds share. Work on branch [BASE BRANCH from the branch session], in a new git worktree and a new branch ui/foundation.

Read first: the accessibility-map skill, docs/ux_brief.md, docs/design/CHOSEN_DESIGN.md (my choices), the chosen style files in docs/design/style/, docs/architecture.md, and the current UI code and styles.

Build only the shared base, no screens:
1. One tokens file (CSS custom properties for colour in light and dark, type, spacing, radius, shadow, motion with reduced-motion) from the chosen style.
2. The icon set as a single self-hosted SVG sprite or small module, with the exact icons in the style board and accessible names.
3. Shared component styles and small helpers (button variants, chips, fields, cards, rating badge, bottom sheet, banner, toast, empty and error states, focus ring), named so the map, report and chat builds can use them without editing each other's files.
4. Self-hosted fonts if the style needs them (free, OFL), no third-party requests.
5. A components test page that shows each component in every state, light and dark, and a script that checks contrast, target sizes (44 px), and that nothing is requested from another host.
6. Write docs/design/COMPONENTS.md: a short list of components, their class names and how to use them, so the three area builds do not conflict.

Before editing, write a plan with the files you will change. Add tests, check at 375 px and 1280 px, take screenshots. Do not restyle the existing screens yet. Update docs/architecture.md (Mermaid), docs/decisions.md, docs/progress_log.md. Run the gitleaks hook and commit as zenaism@miamioh.edu; do not push or merge. Do not stage my unrelated modified files.
```
PROMPT END

---

## Prompts B1, B2, B3: Build each area (run in parallel after B0 is merged to the base branch)

B1 = map, search, details, live navigation and favourites. B2 = report a problem. B3 = chat, voice and settings. Fill in the brackets and run each in its own worktree and branch.

PROMPT START
```text
Build session [B1 map / B2 report / B3 chat] for the Accessibility Map. Work on branch [BASE BRANCH including B0], in a new git worktree and a new branch [ui/map, ui/report or ui/chat].

Read first: the accessibility-map skill, docs/ux_brief.md, docs/design/CHOSEN_DESIGN.md (my choices for this area), the chosen frame files in docs/design/[map, report or chat]/, docs/prototypes/CHOSEN.md, docs/design/COMPONENTS.md, docs/architecture.md, and the code you will change. The shared tokens, icons and components come from B0: use them, do not edit them. If something is missing from B0, tell me and stop.

Steps:
1. Write a short plan: the files you will change, the tests, the risks. Change only those files. Two other area builds run at the same time on other files.
2. Build the area to match the chosen frames, including every state shown. Free tools only, no paid APIs, no manual data checking. Location, favourites and drafts stay on the device. Keep text short, as in the frames.
3. Add tests (unit tests for logic, browser checks at 375 px and 1280 px). Run the fast test tier and report any failures, including ones you did not cause.
4. Check the brief's accessibility checklist and report measured results: contrast, keyboard only, screen reader names and errors, focus order, 44 px targets, reduced motion, 200 percent zoom, dark mode.
5. Run the app, take screenshots of each state and compare them with the frames; list every difference and why.
6. Update docs/architecture.md (Mermaid), docs/decisions.md, docs/system_overview.md, docs/progress_log.md and the "Progress and to-do" section.
7. Run the gitleaks hook and commit as zenaism@miamioh.edu. Do not push or merge.

If something in a frame cannot be built as drawn, stop and tell me instead of improvising. Do not stage my unrelated modified files.
```
PROMPT END

---

## Prompt 5 (updated): Final review

Use Prompt 5 from docs/session_prompts.md, with these extra lines added at the end of its numbered list:

PROMPT START
```text
8. Compare each finished screen with its chosen frame in docs/design/ and list the differences.
9. Check visual consistency: the same icons, colours, spacing, corner radius, button styles and short wording on map, report and chat, in light and dark mode.
10. Check that no text is longer than the content style guide allows, and that every button with an icon also has a text label or an accessible name.
11. Check that no request goes to another host (fonts, icons, scripts) in the browser network log.
```
PROMPT END
