> **Archived 2026-11-27.** Historical record: this was built, answered or superseded. Current docs: [`../README.md`](../README.md), [`../decisions.md`](../decisions.md), [`../ui_handout.md`](../ui_handout.md).

# Session prompts for the UI/UX redesign

Copy one block at a time into a separate Claude session. Each block is between the lines `PROMPT START` and `PROMPT END`.

## Order and parallel runs

| Step | Prompt | Run | Notes |
|---|---|---|---|
| 0 | Reply to session 1 (answers) | now, in the session that wrote the brief | Fill the two bracketed items first |
| 1 | 3 Branch consolidation | after 0, alone | Plans only; asks before merging. Must finish before any build |
| 2 | 2A, 2B, 2C prototypes | after 0, all three in parallel | Each writes only to its own folder |
| 3 | You review prototypes and choose options | | |
| 4 | 4 Quick fixes (touch targets) | after 1, any time | Small, no prototype |
| 5 | Build 4A (map) and 4C (chat) | after 1 and approval, in parallel | Use separate git worktrees |
| 6 | Build 4B (favourites) | after 4A finishes | Both edit the map page |
| 7 | 5 Final review | last, alone | |

---

## Prompt 0: Reply to session 1 (answers to the open questions)

PROMPT START
```text
My answers to the open questions in docs/ux_brief.md:

Q1: Yes, deploy/routing-pages is the source of truth for the UI. Do not merge anything in this session; a separate session will handle the branches. My iPhone model and iOS version: [FILL IN, or write "I will check later"].
Q2: The gear icon I see: [ATTACH SCREENSHOT AND SAY WHICH DEVICE AND PAGE, or write "not available"]. Until then, plan to replace it with a standard gear icon (inline SVG) with a text label.
Q4: Yes. Navigation v1 is a follow-me dot, an accuracy ring, direction, and the next step as text only. No spoken turns, no re-routing, no off-route alerts.
Q5: Yes. Saved places stay on the device with a copyable restore link, and there is no Supabase sync.
Q6: Yes. The first layer of the details panel holds the rating word, entrance, restroom, one step or parking line, source and age, then "Route here" and "Save".
Q7 and Q9: Yes to both. Chat gives one sentence plus one place card, with the rest under "More". Voice is tap to start and stop, capped at 60 s, with an editable transcript and no auto-send.
Q8: Yes. The map is empty on open, the list shows only Saved plus a prompt, and "Browse A to Z" stays.
All other questions (the full 13 in section 11): accept your recommended defaults.

Now finalize:
1. Update docs/ux_brief.md with these answers and mark section 11 as answered.
2. Write the decisions (with the why) in docs/decisions.md and update docs/architecture.md (Mermaid), as promised.
3. Check that the screen inventory and prototype session plan (section 10) say clearly which branch every prototype must target and that no prototype may edit app code.
4. Commit ONLY the docs files you changed (ux_brief.md, decisions.md, architecture.md, progress_log.md, README.md, the docs/figures/ux_audit screenshots) as zenaism@miamioh.edu. My working tree has many unrelated modified data files; do not stage them. Run the gitleaks hook. Do not push.
5. Tell me the commit and that the brief is final.
```
PROMPT END

---

## Prompt 2A: Prototype, map and navigation (items 1, 3, 7)

PROMPT START
```text
Prototype session 2A for the Accessibility Map. Produce clickable HTML prototypes for my review. Do NOT touch src/, the live web pages or data, and do not build the real feature. Write only inside docs/prototypes/map/.

Read first: the accessibility-map skill, docs/ux_brief.md (final; follow its style guide, accessibility checklist, constraints and my answered questions Q4, Q6 and Q8), docs/architecture.md, and the current deployed UI code on branch deploy/routing-pages (worktree accessibility-map-integration; read it, do not edit it). Look at the screenshots in docs/figures/ux_audit/.

Scope, three parts on the same screen:
- 2A.1 Live location and heading (decision Q4). A follow-me dot that moves as the person moves, an accuracy ring, a heading arrow or cone, and the next step as text only. No spoken turns, re-routing or off-route alerts. Cover the "locating" state, poor accuracy, permission denied, no compass, the iOS compass permission button (must come from a tap), the control to re-centre or stop following, and battery use (when to stop watching). Location stays on the device.
- 2A.2 Search-first map (decision Q8). The map is empty on open. The list shows only Saved places plus a prompt, and "Browse A to Z" stays. Design the empty map, the search box and suggestions, results on the map and as a list, clearing a search, no results, and how nearby places can be found without typing. Also fix the audit findings in the first view (26 icons, about 20 cluster discs, trail lines, Report button): say what stays on the empty map.
- 2A.3 Details panel (decision Q6). First layer: rating word, entrance, restroom, one step or parking line, source and age, then "Route here" and "Save". Everything else behind "More details". Show the "Area History" example (now 1,598 characters) in the new layout, with unknown values, long names and a 5-step route.
All touch targets are at least 44 px; fix the audit's 32 px "Near me" and "Ask" and the 13 px header "!" button in the prototype.

Deliver in docs/prototypes/map/:
- 2 or 3 options per part as standalone HTML files with fake data. Work at 375 px and desktop widths. No external dependencies except the map library the project already uses.
- index.html linking the options with a short comparison table, and a states page with every state (loading, empty, denied, error, long names, many results).
- README.md with a Mermaid flow diagram.
- An accessibility self-check against the brief's checklist, with measured contrast values and the keyboard path.
- For each part, your recommendation with reasons, and the questions I must decide.

Rules: free tools only, no paid APIs, minimal accessible style. Follow the skill and my memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu (my working tree has unrelated modified files; do not stage them). Do not build. Wait for my choices.
```
PROMPT END

---

## Prompt 2B: Prototype, favourites page (item 2)

PROMPT START
```text
Prototype session 2B for the Accessibility Map. Produce clickable HTML prototypes of the favourite buildings feature for my review. Do NOT touch src/, the live pages or data, and do not build the real feature. Write only inside docs/prototypes/favourites/.

Read first: the accessibility-map skill, docs/ux_brief.md (final; follow its style guide, accessibility checklist and my answered question Q5), docs/architecture.md, docs/compliance.md, and the current saved-places code on branch deploy/routing-pages (worktree accessibility-map-integration; read it, do not edit it). Today there are hearts and a "Saved places" filter stored in localStorage, but no page, no way to move them to another device, and no warning if the browser clears storage.

Design (decision Q5: saved places stay on the device with a copyable restore link, no Supabase sync):
- How a person saves and removes a favourite from the map, the details panel and search results: the control, its states, and feedback for screen readers.
- The favourites page: list order, what each row shows (name, key access facts, freshness), sorting and grouping, a small map view, empty state, and many favourites. Where it lives in the navigation, reachable one-handed on a phone.
- The restore link: how it is created, copied and used, a warning before storage might be cleared (Safari can delete script-written storage after 7 days without a visit), and what the person sees after restoring. Show how the link avoids putting personal data on a server.
- How a place that disappears or changes is handled.
- Whether the chat can use favourites ("is my favourite cafe step-free?"); show one example.

Deliver in docs/prototypes/favourites/:
- 2 or 3 options as standalone HTML files with fake data, working at 375 px and desktop widths.
- index.html with a comparison table, a states page (empty, one, many, offline, place removed, restore success and failure), and README.md with a Mermaid flow diagram.
- An accessibility self-check against the brief's checklist, with all touch targets at least 44 px.
- Your recommendation with reasons, and the questions I must decide.

Rules: free tools only, no paid APIs, minimal accessible style. Follow the skill and my memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu (do not stage my unrelated modified files). Do not build. Wait for my choices.
```
PROMPT END

---

## Prompt 2C: Prototype, chat (items 4, 5, 6, 8)

PROMPT START
```text
Prototype session 2C for the Accessibility Map. Produce clickable HTML prototypes of the chat assistant UI for my review. Do NOT touch src/, the live pages or data, and do not build the real feature. Write only inside docs/prototypes/chat/.

Read first: the accessibility-map skill, docs/ux_brief.md (final; follow its style guide, accessibility checklist and my answered questions Q2, Q7 and Q9), docs/assistant_design.md, docs/assistant_build_spec.md, and the current chat code on branch deploy/routing-pages (worktree accessibility-map-integration; read it, do not edit it). Look at the screenshots in docs/figures/ux_audit/.

Scope:
- 2C.1 Settings icon (Q2). The live button is a custom SVG that looks like a sun, not a gear. Replace it with a standard gear (inline SVG, no icon library) and a visible or screen-reader label. Show the settings panel contents as they exist today. If I attached a screenshot of the icon I see, use it.
- 2C.2 Concise answers (Q7). One sentence plus one place card, the rest under "More", with follow-up chips. Today one answer is 1,465 characters: three full place cards plus 5 extra buttons. Use three real questions from the repo's test or eval files and show each in short and expanded form. Say what the short form must include (key fact and confidence), what moves under "More", and how sources and unknowns appear. Include a draft instruction for the assistant's prompt that produces this length (a draft only, not a code change).
- 2C.3 Layout. The compose area uses about 20 percent of the screen, and the last buttons end 38 px above the edge in Chromium. I reported a cut-off on my phone [iPhone 16 Pro, iOS version not checked]. Design the layout so the input and buttons are always above the bottom edge: use dvh, the iOS safe area, the on-screen keyboard, landscape and 200 percent zoom, and a smaller compose area. Show scrolling behaviour of the message list. Raise "Near me" and "Ask" from 32 px to at least 44 px.
- 2C.4 Voice input (Q9). Tap to start and stop, capped at 60 s, with a visible counter, an editable transcript and no auto-send. The browser ends recognition at the first pause (the code sets continuous = false), so show the design that restarts recognition when it ends and keeps what was said. Show every state: idle, recording, restarting, processing, error, mic denied, limit reached (never discard audio or text silently).

Deliver in docs/prototypes/chat/:
- 2 or 3 options for 2C.2 and 2C.3, and one for 2C.1 and 2C.4, as standalone HTML files with fake data, working at 375 px and desktop widths.
- index.html with a comparison table, a states page (long answer, error, offline, mic denied, keyboard open), and README.md with a Mermaid flow diagram.
- An accessibility self-check against the brief's checklist.
- Your recommendation with reasons, and the questions I must decide.

Rules: free tools only, no paid APIs, local models allowed. Follow the skill and my memory notes: record decisions and reasons in docs/decisions.md, update docs/progress_log.md, commit only your own files as zenaism@miamioh.edu (do not stage my unrelated modified files). Do not build. Wait for my choices.
```
PROMPT END

---

## Prompt 3: Branch consolidation (run before any build)

PROMPT START
```text
Branch session for the Accessibility Map. The UI code (chat, routing panel, saved places, voice) lives on feature/assistant, feature/browser-routing and deploy/routing-pages, and the worktree accessibility-map-integration has uncommitted edits. main does not have it. My design brief says deploy/routing-pages is the source of truth for the UI. Before any build session can start, I need one clean branch to build on.

This session is PLAN FIRST. Do not merge, reset, delete, push or discard anything until I approve the plan.

1. Inspect, read-only: list all branches and worktrees, what each has that the others lack (commit lists, file diffs), the state of the uncommitted edits in accessibility-map-integration (list the changed files and summarize each change), and what is deployed on GitHub Pages and from which branch. Draw a Mermaid diagram of the branch relationships.
2. Propose a plan to get a single branch that contains the UI and that the build sessions can branch from: which branch becomes the base, the merge order, how to handle the uncommitted edits (commit to a branch, never discard), conflicts you expect, and how to roll back. Prefer plain merges. Do not rewrite history. List every command you would run.
3. Check that the base branch passes the fast test tier and the gitleaks hook, and report any failure (including ones you did not cause).
4. Wait for my approval. After I approve, run the plan, verify the app starts and the deployed pages still work, and commit as zenaism@miamioh.edu. Do not push until I say so.
5. Record the why in docs/decisions.md, update docs/architecture.md and docs/progress_log.md.

My working tree on main has many unrelated modified data files. Do not stage, commit or reset them.

Additional facts from the brief session. Include them in your inspection and plan:
- main has diverged from origin/main: 48 local commits against 102 on the remote. A plain push is rejected. Find out what the remote has that local main lacks, and what local main has that the remote lacks, and whether the 102 remote commits are the UI branches or other work (for example automated data updates). Propose merge or rebase with reasons. Prefer a merge (no history rewrite) unless the evidence says otherwise, and show me the expected conflicts before doing anything.
- Do not push, merge or rebase until I approve the plan.
- The 61 data/cards/* files, config/sources.yaml and docs/source_inventory.md are modified and uncommitted. They are the daily card regeneration. Do not commit, stage or reset them. Explain how they will be protected during a merge (for example by a named stash), and how they come back.
- docs/progress_log.md was modified again after the brief session committed. Several sessions edit it. Tell me what changed and suggest a way to avoid conflicts when sessions run in parallel.
- The untracked planning docs (assistant_plan.md, assistant_build_spec.md, crawler_guide.md, implementation_plan.md, routing_in_browser_plan.md, session_prompts.md) are mine and must survive. Tell me if any of them exists on the remote under the same name.
- The brief session made two local commits (e1b98aa, d22ea7d) on main. Their 19 screenshots in docs/figures/ux_audit/ were about 13 MB; check they were shrunk, and if the commits were rewritten, use the new ones.
```
PROMPT END

---

## Prompt 4: Quick fixes (touch targets), no prototype needed

PROMPT START
```text
Build session for small accessibility fixes in the Accessibility Map UI. No prototype is needed. Work on the branch the branch-consolidation session produced [BRANCH NAME], in a new git worktree.

Read first: the accessibility-map skill and docs/ux_brief.md (the audit and the accessibility checklist).

Fix: "Near me" and "Ask" buttons are 32 px tall and must be at least 44 px (the repo rule). The header "!" button is 13x13 px; make it at least 24x24 px (WCAG 2.2 AA) and ideally 44 px, keeping its meaning and label. Check other controls with a script that lists every button, link and input under 44 px on the map and the chat at 375 px and 1280 px widths, and report the full list. Fix only what is clearly a bug; list the rest for the build sessions.

Tell me what you found before editing. Then fix, add checks, and take before and after screenshots. Follow the skill and memory notes: record the why in docs/decisions.md, update docs/progress_log.md, run the gitleaks hook, commit as zenaism@miamioh.edu. Change only the files these fixes need.
```
PROMPT END

---

## Prompt 4A / 4B / 4C: Build an approved prototype (template)

Use once per approved prototype. 4A = map and navigation, 4B = favourites, 4C = chat. Fill in the three bracketed parts. Run each in its own git worktree.

PROMPT START
```text
Build session for the approved prototype: [NAME, for example "map and navigation"], located in docs/prototypes/[FOLDER]/. I chose these options: [YOUR CHOICES AND ANY CHANGES]. Work on branch [BASE BRANCH from the branch-consolidation session], in a new git worktree and a new branch named [e.g. ui/map-navigation].

Read first: the accessibility-map skill, docs/ux_brief.md, the approved prototype files and its README, docs/architecture.md, and the code you will change.

Steps:
1. Before editing, write a short plan: the files you will change, the tests you will add, the risks. Change only the files in the plan. Another build may be running in parallel on other files.
2. Build the feature to match the approved prototype, including every state on its states page. Free tools only, no paid APIs, no manual data checking. Location and favourites data stay on the device. All touch targets at least 44 px.
3. Add tests (unit tests for logic, plus browser checks at 375 px and 1280 px). Run the fast test tier and report any failures, including ones you did not cause.
4. Check the brief's accessibility checklist: contrast, keyboard-only use, screen reader labels, focus order, touch target size, reduced motion, 200 percent zoom. Report the measured results.
5. Run the app and take screenshots of each state. Compare them with the prototype and list every difference and why.
6. Update docs: docs/architecture.md (Mermaid), docs/decisions.md (the why), docs/system_overview.md, docs/progress_log.md and the "Progress and to-do" section.
7. Run the gitleaks hook and commit as zenaism@miamioh.edu. Do not push or merge.

If something in the prototype can't be built as drawn, stop and tell me instead of improvising. Do not stage my unrelated modified files.
```
PROMPT END

---

## Prompt 5: Final review (after all builds are merged)

PROMPT START
```text
Final review session for the Accessibility Map UI/UX redesign. Read docs/ux_brief.md and the builds listed in docs/progress_log.md. Check the finished app, not the plan. Do not add features.

1. Run the app and test every task in the brief's top-task list at 375 px, tablet and desktop widths, with keyboard only, and with a screen reader if available. Record pass or fail against each task's success test.
2. Re-run the brief's accessibility checklist on the real pages and report measured values.
3. Check consistency across map, favourites and chat: colours, spacing, icons, wording and states.
4. Check privacy: no location or favourites sent anywhere, no new third-party requests.
5. Check that docs match the app: architecture diagram, system_overview, decisions (statuses), README and progress log.
6. List the problems found, ranked, with evidence. Fix only the small ones (under ten lines each) and tell me about the rest.
7. Follow the skill and my memory notes, run the gitleaks hook and commit as zenaism@miamioh.edu. Do not push.
```
PROMPT END
