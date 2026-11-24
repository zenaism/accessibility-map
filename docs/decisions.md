# Decision log

Every significant choice, with the reasoning, the alternatives we considered and what it costs us. Newest first. Add an entry whenever we decide something non-obvious (a tool, a format, a source, a policy).

**How to read the "Basis" line.** *Recorded* means the reason is written somewhere in the repo (linked). *Inferred* means the decision is real but its reasoning was never written down; I reconstructed the likely reasons from the code and design, and they need a quick confirm or correction from you.

**Template**

```
### D-NN: Title (date, status)
Decision: what we chose.
Why: the reasons.
Alternatives: what else we considered and why not.
Costs / revisit if: what this makes harder, and what would make us reconsider.
Basis: recorded (where) | inferred (confirm)
```

Status is one of: accepted, proposed (not yet approved), superseded.

---

### D-58: Style direction A Harbor chosen over B Signal and C Meadow (2026-11-24, accepted)
Decision: the owner chose A Harbor (teal, soft, Figtree, Lucide). All design frames (map, report, chat) read `docs/design/style/tokens/style-a-harbor.css` and `components.css` unchanged and add only layout rules built from tokens. Supersedes the recommendation of B in D-57.
Why: the owner's choice (no reason stated). Reusing the token files gives a later build the same look from the same files; no colour or icon is invented.
Alternatives: B Signal (recommended in D-57), C Meadow; copying and editing tokens per frame (drifts apart).
Costs / revisit if: B had the heaviest text for low vision; A passes all measured pairs but has no sunlight test. If the direction changes, rebuild with another token file (`lib.py` names the direction; chat re-copies `assets/tokens`).
Basis: recorded (owner's choice in the V2 briefs). Source: [design/map/DECISIONS.md](design/map/DECISIONS.md) V2A-1, [design/chat/DECISIONS.md](design/chat/DECISIONS.md) note 1.

### D-59: Report a problem is the fourth tab on phone and a top-bar button on desktop (2026-11-24, accepted)
Decision: the phone tab bar has four items: Map, Saved, Ask, Report (flag icon, accessible name "Report a problem"). On desktop it is a top-bar button next to Ask. The app bar has no Report button; Settings stays there. The place card and details view keep "Report a problem here", which prefills the place. This replaces the list-footer spot of D-52 and the idea of an app-bar button. Supersedes D-52 (and the "list footer stays as a second route" line in D-V2B-1; the list footer is dropped).
Why: the owner decided it. The tab bar is in the thumb zone, so one-handed outdoor use reaches it; reporting problems is the lab students' main task, so it deserves the same weight as Map and Saved; the bar is on every phone screen, so the spot is the same everywhere (checklist item 18, ux_brief 3.2.6); no floating button covers the map or legend.
Alternatives: app-bar button (top of screen, hard to reach); floating button (covers map and legend, audit A6); list footer only (not on every screen).
Costs / revisit if: four tabs are about 93 to 94 px wide at 375 px (all pass 44 px) but CHOSEN.md warned of a crowded bar; at 188 px (200 percent zoom) labels become hidden names. Test on a real phone. Map, report and chat frames must all use the same four-item bar.
Basis: recorded (owner's decision, V2A follow-up). Source: [design/map/DECISIONS.md](design/map/DECISIONS.md) V2A-2, [design/report/DECISIONS.md](design/report/DECISIONS.md) D-V2B-1, [design/chat/DECISIONS.md](design/chat/DECISIONS.md) note 3.

### D-60: Defaults assumed pending the owner's answer (2026-11-24, accepted by default)
Decision: keep the word "Partly accessible"; dark mode is designed, light is the default; the USGS basemap stays light; Near me and Ask sit under the search; no seventh "Near me" tile because the button is already under the search. Dark mode designed supersedes the light-theme-only line of D-31 for design purposes; whether to ship it is still open (D-57).
Why: the owner did not answer style README questions 1 to 7; these are the defaults the style README and CHOSEN.md already drew.
Alternatives: other wording for partial (README lists them); dark basemap (not available).
Costs / revisit if: the owner answers differently; listed in the map `README.md` under "Assumed defaults".
Basis: inferred, to confirm. Source: [design/map/DECISIONS.md](design/map/DECISIONS.md) V2A-4; [design/style/README.md](design/style/README.md).

### D-61: The partial rating keeps its orange and gets a ring (2026-11-24, accepted)
Decision: `#E69F00` stays. On the map the pin keeps its 2.5 px dark edge and white halo (13:1 on the basemap, 7.95:1 against the fill); the badge and tile get a ring in the badge text colour (`--partial-fg`, 8.9:1 on white, 10.1:1 in dark mode). The chat frames use `--partial-ring` `#8A5300` (6.33:1) in light mode, none needed in dark (6.98:1), and `#B2C4CE` for the unknown grey tile in dark mode (2.59:1). Recommend moving `.badge.partial { border-color: var(--partial-fg) }` into the shared components in the foundation build. Settles the partial-colour open point in CHOSEN.md.
Why: the fill alone is 2.25:1 on white and 1.81:1 on the basemap, below 3:1. A ring needs no new colour, so the Okabe-Ito colour-blind-safe set stays. Text and symbol were never at risk.
Alternatives: a darker orange (breaks the colour family and the measured pin set); no ring (fails 3:1).
Costs / revisit if: the two ring colours (`--partial-fg` and `#8A5300`) should be unified in the foundation build.
Basis: recorded (measured in `contrast_map.csv`). Source: V2A-3, D-V2B-9, chat note 2.

### D-62: Three variants only for the place card, next-step banner, report steps and chat answer and compose (2026-11-24, accepted)
Decision: place card A List, B Rating first, C Sentence first; next-step banner A Card, B Filled, C Distance tile (state frames use A). Report main step A Steps, B One screen, C Sheet; success A Receipt, B Timeline, C Summary on the map. Chat short answer A plain card, B rating band, C big rating tile; compose A one field with icons (12 percent of height), B labelled actions (18 percent, clearest names, worst at 200 percent zoom), C big round mic plus pill (13 percent, for voice users). Everything else has one design. Where and Details are drawn in the A layout only.
Why: the owner asked for three variants of the most important components only; structure is fixed by CHOSEN.md, so variants differ in look or taps, not in the chosen structure. Report success B makes "Report another" primary (many lab reports in a row).
Alternatives: variants for every screen (too much to choose from).
Costs / revisit if: after the owner picks, the board session can drop the others.
Basis: recorded. Source: V2A-5, D-V2B-8, chat notes 5 and 6.

### D-63: Frames are generated by script and measured in a real browser (2026-11-24, accepted)
Decision: `build.py` generates every frame; `check.py` opens each in Chrome and measures target size, text contrast, names, overflow and external requests; `check_contrast.py` measures token pairs. Chat frames fill their window instead of fixed boxes (manifest gives the intended size); 200 percent zoom is shown as a 188 x 406 px viewport (compose area then takes 41 to 70 percent of the height).
Why: measured results instead of estimates; one generator keeps the frames consistent when a token or word changes; real dvh and zoom behaviour can be tested.
Alternatives: hand-made frames (drift).
Costs / revisit if: not covered: real screen readers, real phones, forced colours, sunlight.
Basis: inferred (owner asked for a measured self-check). Source: V2A-6, chat notes 9 and 10.

### D-64: Report form: text optional, two or three steps, no map pin (2026-11-24, accepted)
Decision: "What happened" is Optional; when empty the build sends the kind label (for example "Blocked, broken") as the text, because `supabase/problem_reports.sql` requires 5 to 1000 characters. From a place card the form has What, then Details (2 steps); from the Report tab it adds Where (search, Near me, "Not about one place") for 3 steps; cue "Step n of N" with a bar; one dialog on desktop. No free map pin.
Why: fewest taps, often outdoors with one hand; a prefilled place saves a screen; the table stores link_id, place_name and region only, with no latitude or longitude, so a pin would be thrown away.
Alternatives: relax the check to 0 (SQL change the owner must run); always 3 steps; add lat and lon columns (new privacy question, a pin can be a home address).
Costs / revisit if: the team sees only the kind for some reports; a problem not at a listed place (a broken kerb ramp mid-block) cannot be pinned.
Basis: recorded (SQL read) plus inferred. Source: D-V2B-2, D-V2B-3, D-V2B-4.

### D-65: Report wording says what the code does (2026-11-24, accepted)
Decision: privacy line "No name needed. We keep your report, device type and page address." plus a "What we keep" sheet (mentions the random device code, which makes Delete work). Offline says "Your text is saved on this device" with Try again, not "Reports send when you reconnect". Duplicate says "Already sent. Your code is X." as information, not an error. Errors: a summary at the top takes focus (tabindex -1) with links to each field; each field has its own message via aria-describedby (aria-invalid on text fields, a fieldset for choice groups); no role=alert on the summary, so it is read once.
Why: the code stores user agent, page address, a device code and optional contact, so "Anonymous" over-promises (improvement_plan 3.6, audit A14); it keeps a draft but never sends later by itself; a repeated report id is stored once; improvement_plan 3.7 found errors not tied to fields and a summary announced twice.
Alternatives: keep "Anonymous"; build send-when-online (needs a queue and online listener, out of scope).
Costs / revisit if: the "no IP address" claim holds for our table only (Supabase request logs not checked); retention of 24 months is still the owner's proposal to confirm (compliance.md section 4); an offline person must press Try again; the photo is lost if the form is closed.
Basis: recorded (code read). Source: D-V2B-5, D-V2B-6, D-V2B-10.

### D-66: "My reports on this device" list is optional and needs a small build (2026-11-24, proposed)
Decision: one frame draws the list (kind, place, date, code, Delete) with an "only on this device" note. It is not in the current system. Building it means saving the report id and device code in the browser at send time, then using the existing delete function.
Why: the code stores no ids and has no read function today; the cost is small, so drawing it lets the owner decide.
Alternatives: no list (people cannot find their code or delete later).
Costs / revisit if: no status column (the public key cannot read the team's status); clearing browser data empties the list while reports stay in the database for up to 24 months.
Basis: recorded (owner: optional, small build). Source: D-V2B-7.

### D-67: Chat frames: chips live in the list, one Stop, separate live regions (2026-11-24, accepted)
Decision: quick chips are removed from the compose area (the greeting offers questions and each answer ends with three follow-up chips); while recording the compose mic is dashed and named "Speak, listening now" and Stop lives only in the voice bar; the chat list is `role="log"` inside `<main>`, and state messages go to a separate polite region (the counter stays silent).
Why: the chip row cost 56 px and put the compose area at 19 percent, over the 18 percent cap (now 12 to 18 percent); two Stop buttons confused the focus order and CHOSEN.md keeps Stop in one place across Listening, Restarting and Processing; one live region for answers and one for short state text.
Alternatives: keep the chip row; one shared live region.
Costs / revisit if: testing shows people miss the greeting chips once the list scrolls.
Basis: inferred (needs confirming). Source: [design/chat/DECISIONS.md](design/chat/DECISIONS.md) notes 4, 7 and 8.

### D-57: Three style directions proposed; recommend B Signal, owner has not chosen (2026-11-24, proposed; owner chose A, see D-58)
Decision: three directions were built as a style board ([design/style](design/style/index.html)): A Harbor (teal, soft, Figtree, Lucide), B Signal (ink, bold, Atkinson Hyperlegible, Tabler), C Meadow (green, pill shapes, Lexend, Phosphor). Each has light and dark tokens in its own CSS file. Recommendation: B, then C, then A. The structure is the one in `prototypes/CHOSEN.md`; only the look differs.
Why: the audience is outdoors on phones, many with low vision or tremor; B has the heaviest text and borders, solid badges and a font built for low vision (Braille Institute page read). All 240 colour pairs (text 4.5:1, controls 3:1) pass in all three, light and dark, computed by `palettes.py`. Fonts are SIL OFL and icons ISC or MIT, all self-hosted and inlined, so the page makes no outside requests (privacy rule).
Alternatives: keep the grey minimal look (the owner no longer wants it as the target); a dark basemap (not available: the USGS basemap stays light, so pins use fixed colours with a dark outline and white halo in both modes).
Costs / revisit if: dark mode was ruled out for v1 (Q13) but is designed here and passes, the owner decides whether to ship it; the pattern research (bottom sheets, floating search, status badges) is *assumed*, one source did not load; no screen reader, real phone or sunlight test yet; Lexend is wide, long place names need a check.
Basis: recorded (owner's V1 request); measurements are computed, pattern claims assumed.

### D-49: Live location uses the bottom card (2A.1 option A) (2026-11-24, accepted)
Decision: follow-me dot, accuracy ring and next step use the bottom card layout; Stop is kept visible above notices; stop after 5 minutes without moving; Previous and Next step always shown; 50 m rough limit.
Why: dot and next step are on screen together and every control is in the thumb zone; one reading order. Recommended by the prototype README ([prototypes/map/README.md](prototypes/map/README.md)); the open questions took their stated defaults.
Alternatives: B top banner (text far from the thumb, hides map), C text-first (least map).
Costs / revisit if: a long notice pushes lower controls to the screen edge; thresholds are untuned; needs an iPhone and an Android test before building.
Basis: recorded (README recommendation, owner acceptance in session V0); defaults taken, not stated by the owner. See [prototypes/CHOSEN.md](prototypes/CHOSEN.md).

### D-50: Search-first map uses tiles with a chip row above results (2A.2 option B) (2026-11-24, accepted)
Decision: six large tiles (Near me is one) in the list; chip row above results; C's "Search this area" and distance choice come later; half-mile default radius; empty sheet half height on phone.
Why: all choices visible at 375 px, big low targets, shorter header. README recommendation.
Alternatives: A chips (half hidden), C near me first (better for nearby, taken later as refinements).
Costs / revisit if: the half-height sheet makes the map small on first open; half a mile may be too far for a wheelchair user.
Basis: recorded (README, owner acceptance); radius is a default, not measured.

### D-51: Details panel uses inline More details (2A.3 option A) (2026-11-24, accepted)
Decision: first layer then an inline More details; step line rule parking, else step, else Not known; no extra confidence word beyond the rating; steps shown in full.
Why: one tap, nothing replaced, state announced. README recommendation.
Alternatives: B drill-in (hides the map), C sentence first (380 characters, extra tap).
Costs / revisit if: screen-reader users find C's sentence useful; long routes may need a collapsed list.
Basis: recorded (README, owner acceptance); defaults taken.

### D-52: Report a problem sits in the list footer, a default to confirm (2026-11-24, superseded by D-59)
Decision: keep Report a problem in the list footer on phone and in the header on desktop, as in the prototypes.
Why: the floating button covered the map and collided with the legend (audit A6). It is the prototype default.
Alternatives: floating button; one fixed place on every screen (checklist item 18), which the prototypes do not yet meet.
Costs / revisit if: it is harder to find on a phone; the V2 designs should try a fixed entry on every screen and show the owner.
Basis: inferred (README open question B, default taken; owner has not stated it).

### D-53: Favourites use the Saved tab and page with C's Edit list (2B option A) (2026-11-24, accepted)
Decision: bottom tab Saved (n) and a Saved page; name "Saved places"; device snapshot; all change notices; redirect table and one small shared index in the release; no file download; assistant may read the list on the device; link warning as a private note.
Why: only A puts the way back in the thumb zone on every screen, and the restore link needs a plain landing page. README recommendation; open questions took the recommended answers.
Alternatives: B sheet over the map (fallback if the 56 px tab bar is too crowded), C text-first (Saved feels buried).
Costs / revisit if: the tab bar crowds the map on a real phone; the redirect table and shared index change the export (data_dictionary.md); Safari 7-day storage limit.
Basis: recorded (README, owner acceptance). Confirms D-40 to D-44 (favourites).

### D-54: Settings cogwheel and short chat answer shape A (2C.1, 2C.2) (2026-11-24, accepted)
Decision: own-drawn cogwheel, 44 px; chat answer is a sentence, one card, More, three chips; confidence line always shown; the nearest confirmed fresh place leads. C is the fallback.
Why: standard symbol with no licence to carry; 344 to 410 characters against 612 to 943; reuses the place card. Q7 default.
Alternatives: Lucide or Feather gear; B fact list (breaks one system); C sentence only.
Costs / revisit if: the visual design adopts an icon set that has a gear (use that one); confidence line departs from the Q12 quiet default for list cards.
Basis: recorded (README, owner acceptance); lead rule and confidence line are defaults.

### D-55: Chat layout C: compose area under about 18%, two columns in landscape (2C.3) (2026-11-24, accepted)
Decision: layout C; Near me and Ask at 44 px with Ask as the primary header button; blue and teal chat colours dropped for the chosen style.
Why: 18% of a 700 px phone (about 25% today), best landscape list, every control one tap. README recommendation.
Alternatives: A (no landscape gain), B (tray hides Photo and chips).
Costs / revisit if: iOS Safari keyboard and `dvh` behaviour is unverified; two layouts to maintain.
Basis: recorded (README, owner acceptance); measured in Chromium only.

### D-56: Voice input as designed (2C.4) (2026-11-24, accepted)
Decision: continuous recognition with restart after 350 ms, 60 s cap, counter, editable transcript, never auto-sent, text box read-only while listening.
Why: keeps what was said across browser pauses (D-48). README recommendation.
Alternatives: typing counts as Stop; hold-to-talk (rejected in D-39).
Costs / revisit if: real Chrome and Safari engines differ; test on the owner's iPhone over https (pushing the prototype pages is not yet decided).
Basis: recorded (README, owner acceptance); read-only box is a default.

---

### D-44: Favourites UX: recommend a Saved tab and page (option A) (2026-11-23, accepted 2026-11-24)
Decision: three prototypes were built ([prototypes/favourites](prototypes/favourites/index.html)): A bottom tab and Saved page, B Saved sheet over the map, C text-first compact page. Recommendation: A, with C's "Edit list" and compact rows for long lists. Nothing is built until the owner chooses.
Why: A puts the way back in the bottom thumb zone on every screen (task 5, one-handed); the restore link needs a plain landing page that can confirm and report success or failure; a page works without the map (checklist 15). B adds no bottom bar but hides the restore prompt behind a map and sheet; C is simplest but its link is at the top of the screen.
Alternatives: B and C (see the comparison table in the prototype index).
Costs / revisit if: A adds a 56 px tab bar to a map screen that already has a sheet, legend and Report button; test on a real iPhone (checklist 24). If it is too crowded, use B.
Basis: recorded (owner's session 2B request and Q5); effort and one-handed reach are *assumed*, not measured on a device.

### D-43: The assistant may read the saved list on the device (2026-11-23, accepted 2026-11-24)
Decision: a question such as "is my favourite cafe step-free?" is resolved against the saved list in the browser. One saved match gives a direct answer (one sentence plus one card); several matches ask "which one?" with buttons; none offers a search; a closed or removed place says so first. The list is never added to anything that leaves the device.
Why: top task 4 and 5; the assistant already runs on the device (guided mode, local model); keeps the privacy rule.
Alternatives: no personalisation (the question cannot be answered); sending the list to a model (violates privacy and the $0 rule if hosted).
Costs / revisit if: a hosted model is ever used; then saved places must stay out of its prompt.
Basis: recorded (owner request); the on-device behaviour is a design, not tested with the real composer.

### D-42: A small snapshot on the device handles changed and removed places (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: next to each saved id the device keeps name, type, city, last seen entrance, restroom, parking and rating, with source and date. It is never put in the restore link. The Saved page uses it to show a place that left the data (by name), to work with a weak connection (labelled "as last seen"), and to say what changed. Places that merged follow an old-id to new-id table that the data release would carry, written automatically by the dedupe step. Changed, closed, moved and removed places sit first under "Needs a look"; "Caution" and a warning colour only when a fact got worse.
Why: a saved id alone cannot say what a place was called, or what changed; no one can check data by hand, so the release must say when an id moved.
Alternatives: ids only (missing places become codes; no change notices); keep every fact in the link (bigger link, more to leak).
Costs / revisit if: the redirect table is a data-export change to coordinate in `data_dictionary.md`; the snapshot is a little more data kept on the device; after a restore the "changed since" baseline starts again from today.
Basis: recorded (owner's request to handle places that disappear or change); the redirect table and snapshot are my design, *proposed*.

### D-41: Restore link in the URL fragment, merge by default, backup status shown (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: link form `saved.html#restore=v1;<region>~<id>,...;k=<check>` (place codes in saved order and a 4 character check). Browsers never send the fragment to a server, so nothing about the list reaches a server. Opening or pasting a link asks first: "Add" (default) or "Replace" (separate red button naming how many places go). A cut-off, wrong-version or non-link input changes nothing and says why. The page strips the fragment from the address after reading it. The Saved page shows backup status ("not copied yet", "N changes since", "copied N days ago") and, only for Safari after 4 or more days away without a current copy, a warning. The empty page has a paste box.
Why: Q5 and D-36; Safari can delete script-written storage after 7 days (excerpt-level sources in ux_brief 4.4); a link that is cut by a messaging app is common, so a check code and a paste box are needed.
Alternatives: Supabase sync (stores more, uses quota, already rejected); download a file (not offered now; asked in the prototype questions); showing the link only on request.
Costs / revisit if: anyone who gets the link can see the places (a clinic, for example), and apps that send it can read it; the warning cannot reach someone who never returns after 7 days; Safari detection from the user-agent is fragile; whether Home Screen apps are exempt is unverified.
Basis: recorded (Q5, `compliance.md` privacy rules); the fragment rule is standard URL behaviour, *not re-verified in a source here*; the format is my design.

### D-40: Save control: one visible word, no aria-pressed, undo on the Saved page (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: Save is a 44 px button with a heart and the word Save or Saved (filled heart and a thicker border when saved). The word changes; `aria-pressed` is not used. Its name starts with the visible word and ends with the place name. One polite status message for the page announces the result. Removing on the Saved page leaves an inline message with Undo and moves focus to it; elsewhere pressing Save again is the undo. No timed toast. No Save in the map popup.
Why: the current code sets both a changing word and `aria-pressed` (`map_viewer.py:512-516`), which can read as "Saved, Saved, toggle"; timed toasts can vanish before they are read (checklist 16); popup stays short (brief 7.5).
Alternatives: aria-pressed with a fixed word (weaker for low-vision users who read the word); toast with Undo (timing, focus).
Costs / revisit if: a screen reader test shows the status messages are missed.
Basis: recorded (brief checklist 5, 6, 16; read the current code); screen reader behaviour is by design and not listened to.

### D-42: Details panel first layer, built from Q6, with the layout still open (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: first layer = name, rating word with symbol, Entrance, Restroom, one step or parking line, source and age, Route here, Save; everything else behind "More details". Unknown values read "Not known" plus one next-step sentence. Prototyped three ways (inline, drill-in view, sentence first); the owner picks. My recommendation is inline.
Why: Q6 default; the measured live panel showed 1,598 characters at once. In the prototype the Area History first layer is 272 characters and the full content 1,496 (with a route).
Alternatives: drill-in (second view, hides the map); sentence first (380 characters, repeats the rows, one more tap).
Costs / revisit if: screen-reader users find the sentence helps; the facts table needs a `confidence` export field (D-31, not changed here).
Basis: recorded (Q6, ux_brief 3c item 3); layout recommendation is mine, from taps and focus behaviour, not tested with people.

### D-41: Search-first map: what stays on the empty map, and where Report and Legend go (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: the empty map shows only the basemap, zoom buttons and credit (plus a short hint). No markers, no cluster discs, no trails. "Report a problem" moves from a floating map button to the list footer; the legend appears only when results are on the map; "Show all places on the map" is an off-by-default button. Results sort best-known first (accessible, reported, partly, not, then no information), then nearest. On a phone the map sits above the list sheet instead of behind it. Three ways to find places without typing are prototyped (chips, tiles, near me first); my recommendation is tiles, with a chip row once results show.
Why: Q8 and D-37; audit finding 7 (26 icons, about 20 clusters, trails and a button over the map) and A6 (legend and Report collide). The sort rule keeps "no information" below every place that has information (principle 2 in the brief). Map above sheet stops markers and the map credit hiding under the sheet.
Alternatives: keep clustering only (still busy); chips only (half of them are off screen at 375 px); floating Report (covers the map).
Costs / revisit if: "Report" in a footer is harder to find on a phone than a floating button (checklist item 18 wants one fixed place on every screen, not yet true in the prototypes); Near me radius half a mile is a guess for wheelchair users; the layout needs a real phone.
Basis: recorded (Q8, D-37, audit); sort rule, footer placement and radius are inferred from the brief's principles, not stated by the owner.

### D-40: Live location screens: states and limits proposed for the first stage (2026-11-23, accepted 2026-11-24) (number clash, see progress log)
Decision: first stage of Q4/D-35 is a follow-me dot, accuracy ring, heading arrow and next step as text only. Separate states for locating, poor accuracy (over 50 m: says "Location is rough", no arrow, no off-route claim), permission denied (steps still work, moved by hand), no signal, no compass, iPhone compass behind a tap, paused when the page is hidden, stopped after 5 minutes without moving, arrived, stopped. Re-centre and Stop are different buttons ("Follow me" moves the map; "Stop navigation" turns location off). Position changes are never announced; only a new step, arrival, pause and stop are. Three layouts prototyped (bottom card, top banner, text first); my recommendation is the bottom card.
Why: Q4 and D-35 (battery, privacy, `requestPermission()` needs a tap); the brief's checklist item 21. Five minutes idle and 50 m are proposals to tune with real walks.
Alternatives: always-on watching (battery, privacy); one generic error for denied, no signal and rough (hides what the person can still do).
Costs / revisit if: real iPhone or Android behaviour differs (compass, screen lock, accuracy values); spoken steps, off-route alert and re-routing are later stages and need their own screens.
Basis: recorded (Q4, D-35, MDN references in ux_brief 4.2); thresholds assumed; simulated GPS only.

### D-48: Voice keeps what was said across browser pauses (2026-11-23, accepted 2026-11-24)
Decision: recognition runs with `continuous = true`; when the browser ends a session and the person has not tapped Stop, a new session starts after 350 ms and everything heard so far (final or not) is kept. States: idle, starting, recording, warning at 50 s, restarting, processing, stopped, limit reached at 60 s, error, microphone denied, paused by the browser (tap to continue), not supported. The box is read-only while listening; Stop makes it editable; Escape stops; nothing is sent automatically; we store no audio.
Why: the code ended recording at the first pause (`continuous = false`), so long questions were cut. A restart loop is the usual way to get longer input from the browser engine, and keeping interim text means a session that ends without a final result loses nothing. The "paused by the browser" state exists because iOS may refuse an automatic restart.
Alternatives: only raising a timer (does not fix pauses); allowing typing while listening and treating it as Stop (open question for the owner); hold-to-talk (hard with tremor, rejected in D-39).
Costs / revisit if: proven only in a simulation and in Chromium; real Chrome and Safari engines may end sessions differently, so test on the owner's iPhone before building. The 60 s cap is ours; the browser may stop earlier.
Basis: refines D-39. Recorded (owner answer Q9 in [ux_brief.md](ux_brief.md); `voice.js` read on `deploy/routing-pages`) plus inferred (the restart design is mine, not yet tested on a device). Prototype: [prototypes/chat/voice.html](prototypes/chat/voice.html).

### D-47: Chat layout follows the visible screen, compose area at most about 18% (2026-11-23, accepted 2026-11-24)
Decision: the chat shell is exactly the visible viewport (`100dvh` with a `100vh` fallback, plus a `visualViewport` script because iOS Safari does not shrink the layout viewport for the keyboard); only the message list scrolls and the new answer scrolls to its first line (never `scrollIntoView`, which also moved the page in testing); compose padding is `16px + env(safe-area-inset-bottom)` with `viewport-fit=cover`; Speak, Photo and Send are 44 px icon buttons inside the input row, the input is a 16 px auto-growing textarea; Near me and Ask go from 32 to 44 px. Recommended layout: option C (inline icons in portrait, two columns on short wide screens). Option B (one row and a tray) is the alternative.
Why: measured in Chromium, option C gives a compose area of 18% of a 700 px phone (about 25% today), 281 px of list in landscape against 214 px for the other layouts, 16 px above the bottom edge in every size and state tested, no target under 44 px and no sideways scroll at 320 px or 200%. It keeps every control one tap away; B reaches 10% but puts Photo and the quick questions behind a tray.
Alternatives: B (above); keeping today's two rows (about 25%).
Costs / revisit if: iOS Safari behaviour (safe area, toolbars, keyboard, `dvh`) is from search excerpts only and must be tested on a real iPhone; two layouts to maintain in C. 200% zoom was simulated by viewport size.
Basis: recorded (measurements in [prototypes/chat/tools/last_report.md](prototypes/chat/tools/last_report.md); brief section 3c item 6, checklist 8, 10, 24) plus inferred (iOS behaviour). Prototypes: [prototypes/chat/](prototypes/chat/index.html).

### D-46: The short chat answer is one sentence, one card, More, three chips; the nearest confirmed place leads (2026-11-23, accepted 2026-11-24)
Decision: recommended shape A: one sentence of 25 words or fewer, one compact place card (name, rating word and symbol, the key fact, a confidence line with source and month, two actions), a "More" button that opens other places, all facts, quotes and sources, unknowns, contact, Read aloud and Report, and three follow-up chips. The lead place is the nearest one whose record is confirmed and not old; a nearer place with an old or weaker record goes under More with its age. When nothing answers, the sentence starts "I don't know" and the first action is "Report what I know". Draft prompt and tests: [prototypes/chat/answer_prompt_draft.md](prototypes/chat/answer_prompt_draft.md).
Why: your Q7 default (refines D-38). Measured on three eval questions: 344 to 410 characters and 6 buttons against 612 to 943 characters and up to 14 buttons in the rebuilt current shape (the live restroom answer was 1,465 characters). It reuses the place card of the list and map. The lead rule follows the brief's rule that unknown or weak never outranks confirmed.
Alternatives: B, a fact list with no card (breaks one system, D-31 to D-39 principle 10); C, sentence only with the place in a sheet (shortest at 250 to 288 characters, one more tap, kept as the fallback).
Costs / revisit if: the 25-word limit and three chips are proposals, not measured optima; showing the confidence line on every chat answer departs from the Q12 default for list cards (question to the owner); no user testing yet. The live site did not load on 2026-11-23, so "today" was rebuilt from the verified live shape and understates the saving.
Basis: recorded (Q7; [ux_brief.md](ux_brief.md) 3c, 4.4, 4.6; `eval/questions.yaml`) plus inferred (lead rule, limits). Prototypes: [prototypes/chat/answers-a.html](prototypes/chat/answers-a.html).

### D-45: Settings button is a cogwheel drawn for the project (2026-11-23, accepted 2026-11-24)
Decision: replace the sun-like icon (a circle with eight rays) with an 8-tooth cogwheel drawn as inline SVG on a 24 px grid with a 2 px stroke; 44×44 px; "Settings" visible beside it on desktop and as the accessible name on phones; `aria-expanded` and `aria-controls` on the button; the settings panel keeps its current contents and scrolls inside itself (max 60% of the screen).
Why: owner request Q2 for the standard gear (refines D-34). Drawing it ourselves means no icon library and no licence file to carry (Lucide is ISC, Feather is MIT, both would also have been allowed).
Alternatives: an exact Lucide or Feather gear (needs the licence file checked and added); an emoji (never, per the style guide).
Costs / revisit if: the owner prefers a particular gear shape. No screenshot of the icon the owner sees was attached; the live screenshots in `figures/ux_audit/` were used.
Basis: recorded (Q2 in [ux_brief.md](ux_brief.md); `chat.js` icon on `deploy/routing-pages`). Prototype: [prototypes/chat/settings-icon.html](prototypes/chat/settings-icon.html).

### D-42: One UI base branch cut from origin/main; local main is not merged (2026-11-24, accepted)
Decision: build sessions branch from `integration/ui-base`, which is `origin/main` plus three commits (screenshot shrink, side-panel fixes, a lint wrap). Local `main` is left as it is and is not merged or pushed. Old local tips are kept as `backup/*` tags; the uncommitted integration edits live on `wip/panel-fixes`.
Why: `origin/main` already contains the assistant (PR #1), routing, saved places and voice; all three origin UI branches are its ancestors. 46 of local main's 49 commits are patch-identical copies of remote commits, so a merge gives 21 conflicts for no new content. Local history also holds the Google Places files removed by D-41, and merging or pushing it would republish them. Owner instruction 2026-11-24: do not publish Google API data.
Alternatives: merge `origin/main` into local main (rejected: 21 conflicts, republishes Google data); rebase (rejected: rewrites history); use local `deploy/routing-pages` as base (rejected: an older rewritten copy of an origin ancestor).
Costs / revisit if: local main now differs from the remote main until the owner retires it. The daily card regeneration stays uncommitted in the main working tree; commit it from its own branch. Parallel edits to `docs/progress_log.md` still conflict: consider `merge=union` in `.gitattributes`.
Basis: recorded (owner approval 2026-11-24).

### D-41: Saved Google Places details are no longer published (2026-11-23, accepted)
Decision: the three map pages no longer embed Google `google_place` details (accessibility fields, address, Maps link); `google_places_enriched.geojson` and `google_place_matches.csv` are removed from git and git-ignored; `export_map.py` strips the details before rendering pages. Place IDs stay.
Why: Google Places content must not be stored or redistributed (project rule, `SOURCES.md`); the files were public. The owner asked for removal on 2026-11-23.
Alternatives: also rewrite git history (not done: needs a force push on a public repo; owner decision); load details live on selection with a restricted browser key (the older design in the root README).
Costs / revisit if: the maps lose the Google accessibility box; history still holds the old details until rewritten, and clones or forks may keep them.
Basis: recorded (owner instruction 2026-11-23).

### D-40: README rewritten for an outside reviewer; work done on a review branch (2026-11-23, accepted)
Decision: the README is a short front page (animation, status table, three diagrams, five-minute commands, crawler rules, ideas for reviewers) and long material stays in `docs/`. The multi-region animation is built by `scripts/make_regions_gif.py` from real data (OpenStreetMap paths and wheelchair tags for four regions, record counts from `data/cards/index.csv`) plus one assistant screenshot. Work was done on branch `docs/readme-for-review` in a separate worktree, after merging `origin/main`, because `origin/main` already contains the assistant (PR #1) and the working copy of `main` held about 100 uncommitted data-card changes that should not be committed blindly.
Why: a reviewer must understand the project in five minutes; the first draft assumed the assistant was not merged, which was wrong. Status numbers come from `data/cards/index.csv`, not memory.
Alternatives: a Cincinnati-only animation (rejected: misleading); copying doc text into the README (rejected: duplicate docs).
Costs / revisit if: the GIF needs `make data` (local `data/processed`) to regenerate; counts in the README table go stale when sources are re-collected.
Basis: recorded (task brief 2026-11-23).

### D-39: Voice input is tap-to-toggle, continuous, capped, never auto-sent (2026-11-23, accepted)
Decision: tap to start and tap to stop; `continuous = true` with restart when the browser ends a session; 60 s cap with a counter; the transcript lands in the input box, editable; nothing is sent automatically.
Why: the code used `continuous = false`, so the browser ended recording at the first pause and a long sentence was cut off. Tap-to-toggle suits one-handed use and tremor. No auto-send lets people fix recognition errors.
Alternatives: hold-to-talk (hard with tremor); raising a timer only (does not fix the pause cut-off).
Costs / revisit if: iOS Safari is unreliable and the 60 s figure is ours, not the browser's; test on real devices.
Basis: recorded (owner report 2026-11-23; `voice.js:13`; MDN `continuous`; forum reports are excerpts) in [ux_brief.md](ux_brief.md) 3c and 4.4.

### D-38: Chat answers short first, detail on request (2026-11-23, accepted)
Decision: first answer is one sentence plus one compact place card; other places, all facts and sources sit under "More"; at most two visible actions. Every claim stays traceable; computed facts keep "not checked on site".
Why: a measured answer was 1,465 characters with three full cards and five extra buttons; NN/g (April 2026) says to give the essential answer first and let users pull detail.
Alternatives: keep all cards open (wall of text); drop sources from the first answer (breaks the cite-or-unknown rule).
Costs / revisit if: users ask for "More" almost every time.
Basis: recorded (owner request; NN/g page read).

### D-37: Search-first map, no markers on open (2026-11-23, accepted)
Decision: the map opens with the basemap, search, category chips and Near me; markers and trails appear only for a search or chip; "Show all places" is an off switch; the text list and A to Z pages stay complete.
Why: the opening phone view had 26 icons, about 20 cluster discs and trail lines before any question; the owner asked for it. Text-first access is kept for screen-reader users.
Alternatives: keep clustering only (still busy); empty list too (hurts screen-reader and no-map use).
Costs / revisit if: people cannot find places without a query.
Basis: recorded (owner request; measured on the live page). The search-first pattern itself is assumed, no source found.

### D-36: Saved places stay on the device, with a restore link (2026-11-23, accepted by default)
Decision: favourites stay in localStorage; a "Copy link to my saved places" holds place ids only; no account, no Supabase sync; a Saved page replaces the filter-only view.
Why: privacy rules (nothing about people stored), AccessMap keeps profiles on the phone, and Safari may clear script-written storage after 7 days of non-use (excerpt, 2020 to 2022 sources), so a way back is needed.
Alternatives: Supabase sync by random device id (stores more, uses the free quota).
Costs / revisit if: users want several devices to stay in sync.
Basis: recorded (owner chose the default); storage-loss risk is excerpt only.

### D-35: Navigation uses live location only while navigating; spoken steps, off-route alerts and re-routing are built in stages (2026-11-23, accepted)
Decision: `watchPosition` starts only on an explicit Start and stops on Stop, arrival or when the page is hidden; compass only after a button tap; nothing about location leaves the device; build order live dot and text, speech, off-route alert, re-routing; rough GPS says so instead of claiming off-route.
Why: compliance rule that location stays on the device; battery; `requestPermission()` needs a user tap (MDN); owner asked for speech, alerts and re-routing.
Alternatives: always-on tracking (battery, privacy); text only (owner wants more).
Costs / revisit if: spoken steps fail when the iPhone screen locks; the 25 m off-route threshold is a proposal to tune on real walks.
Basis: recorded (owner request, MDN); thresholds assumed.

### D-34: Settings uses the standard gear icon (2026-11-23, accepted)
Decision: replace the sun-like icon with the standard cogwheel (open-licence inline SVG), 44x44, visible name "Settings".
Why: the deployed icon reads as brightness; the owner asked for the gear phones and computers use.
Alternatives: emoji (inconsistent rendering, not recommended).
Costs / revisit if: none; check the icon set licence file when adding.
Basis: recorded (owner, 2026-11-23).

### D-33: Details panel has two layers (2026-11-23, accepted by default)
Decision: first layer = rating word, entrance, restroom, one step or parking line, source and age, Route here and Save; everything else under "More details".
Why: Details on one place showed 1,598 characters at once, with the answer in the first three lines and ten more blocks after it.
Alternatives: keep everything open; a separate page on phones.
Costs / revisit if: testers cannot find hidden facts.
Basis: recorded (owner request; measured).

### D-32: Targets: 44 px is a project rule, 24 px is the WCAG AA minimum (2026-11-23, accepted)
Decision: keep the 44 px primary-target rule and say in the docs that 44 px is the AAA criterion 2.5.5; AA (2.5.8) needs 24 px with spacing exceptions. Control borders `#6b7280`, body text 16 px, muted text `#4b5563`.
Why: one-handed use and tremor; measured failures (32 px header buttons, a 13 px info button, borders at 1.16:1). WCAG pages read 2026-11-23.
Alternatives: meet only AA 24 px.
Costs / revisit if: layouts get crowded on small phones.
Basis: recorded (W3C Understanding pages read; audit measurements).

### D-31: Confidence shown quietly, "Reported accessible" for weak single tags, light theme only (2026-11-23, accepted by default)
Decision: three states (Confirmed, Reported, Not known); labels shown only when weaker or old, always in details; a place with one weak or crowd tag reads "Reported accessible" and sorts below confirmed ones (needs a `confidence` field in the export, flagged for the other team); no dark mode in v1; prototypes are static HTML under `docs/prototypes/`.
Why: the trust engine rates everything but the exported data and UI show none of it; "Area History" ranked first on one OSM tag.
Alternatives: always show confidence (overload); percentages (false precision).
Costs / revisit if: the export change is not agreed with the other team.
Basis: recorded ([ux_brief.md](ux_brief.md) audit A1, A2).

### D-30: The assistant is a tool-first pipeline that runs without a paid model (2026-11-20, proposed)
Decision: there is no funding for a hosted model, so (1) the assistant is built as a fixed pipeline of plan, run tools, compose, verify, with a rules version and a small-local-model version of the plan and compose steps; (2) the public version is a static "guided mode" with no model and no server (quick-ask tiles and a question matcher over exported data); (3) a local small model through Ollama is used for research, evaluation and demonstrations; (4) a hosted model is not used unless funding appears. Details: [`assistant_build_spec.md`](assistant_build_spec.md).
Why: no budget (D-15). Small local models are poor at free-form tool use but acceptable at narrow, schema-constrained steps; the tools and the verifier, not the model, keep answers sourced. A static public version costs nothing, keeps questions on the device, and cannot invent facts.
Alternatives: a hosted model through a proxy (best quality, needs money); a model in the visitor's browser (free but heavy on phones, kept as an experiment); free-tier APIs (limits and terms change, questions go to a third party); a free-form agent loop on a 3B model (unreliable).
Costs / revisit if: free-text understanding in the public version is limited to what rules and the matcher cover; the research claim is about the design, so we must measure rules-only against model-assisted versions honestly; revisit if credits or funding appear.
Basis: recorded (the user stated there is no funding on 2026-11-20; the architecture is proposed and not yet tested).

### D-29: The assistant is named "Openway Assistant" (2026-11-20, accepted)
Decision: the assistant's public name is Openway Assistant; the project and maps stay "Accessibility Map".
Why: includes blind and low-vision users as well as wheelchair users, says what it does, not tied to Ohio. "Ramp Up" was rejected because it leaves out blind users and is a common phrase.
Alternatives: Scout, Levelway, Waymark, Ramp Up.
Costs / revisit if: a quick web search found two small accessibility projects already called Openway (an accessible travel app and a hackathon project); no trademark search was done. Check the USPTO database and ask the professor before publishing, and revisit if there is a conflict.
Basis: recorded (user choice 2026-11-20; web search results).

### D-28: Agreement between sources is measured as corroboration, never as coverage (2026-11-16, accepted)
**Decision:** the trust engine's "agreement" part is the share of what a crowd source *claims* that an independent source backs up within a distance (corroboration), computed by `fusion.py`. What a crowd map *lacks* (coverage) is reported but never lowers its score; the official inventory is not scored by agreement at all. First use, Washington DC: OSM lowered or flush kerbs are corroborated by the official curb-ramp inventory 89% of the time (15 m), audible-signal tags only 29% (25 m).
**Why:** OpenStreetMap is incomplete by nature (it holds 28% of DC's inventoried ramps), so punishing it for what it does not contain would make every crowd source look bad; what matters for believing a claim is whether independent evidence supports it. Conflicts (624 inventory ramps rated "missing" where OSM maps a lowered kerb) are listed as leads, because either source can be out of date.
**Alternatives:** agreement as overlap in both directions (confuses incompleteness with error); no agreement measure (the trust part stays empty).
**Costs / revisit if:** matching by position can pair neighbouring features; the inventory is from 2016, so a low audible-signal figure may reflect newer installations rather than OSM errors; only DC has a configured pair so far; revisit with the same test on Cincinnati (CAGIS) and a field check of a sample of conflicts.
**Basis:** recorded (computed on the fetched DC data; `src/atlas/fusion.py`, 3 tests).

### D-27: Old evidence loses weight at the speed of its kind of fact (2026-11-16, proposed)
**Decision:** a fact's confidence halves after a half-life that depends on what it is about: **14 days** for temporary things (closures, notices, outages, events), **365 days** for operational things (programs, equipment loans, interpreters, captions, contacts, policies, hours), **3,650 days** for physical features (entrances, ramps, elevators, restrooms, surfaces), and 1,095 days for anything unclassified. Classes and numbers are in `config/trust.yaml`; `trust.aged()` applies them.
**Why:** the research to-do "decide how much weight old sources get" has no single answer: a four-year-old ramp survey is still useful, a four-week-old closure notice is not. Treating all ages alike would either bury good old inventories (DC's 2016 ramp survey) or keep stale notices alive. Three classes are simple to explain and to test.
**Alternatives:** one half-life for everything (too crude); no decay and show the date only (the assistant would still need a rule for what to say); learn half-lives from re-crawls (best, needs the change history that only now starts to accumulate).
**Costs / revisit if:** the numbers are educated guesses; physical features can change faster after renovations or construction; revisit once re-crawls and the history archive show how often each attribute really changes.
**Basis:** inferred (my proposal, not yet confirmed by the user or tested against data); implemented and unit-tested.

### D-26: Vision model: llava-phi3 through Ollama, for pictures OCR cannot read (2026-11-16, accepted)
**Decision:** maps, signs and posters whose OCR text is short (under 60 characters) are described by `llava-phi3` (4.2 GB loaded), within a per-crawl budget (`budget.vision_images`, off by default), cached by image hash; the description (kind, summary, accessibility items) is stored as a lead, never as a fact on its own. Only one local model is loaded at a time.
**Why:** the first choice, `qwen2.5vl:3b`, crashes inside the installed Ollama 0.14.1 (a segfault on load, checked in the server log) and `gemma3:4b` needs a newer Ollama; upgrading software on the user's machine was not asked for. `llava-phi3` loads, answers in about 15 seconds per image and described a test sign correctly ("Accessible Entrance, ramp on the left", wheelchair symbol listed).
**Alternatives:** Qwen2.5-VL or Gemma 3 after an Ollama upgrade (better, expected to read maps and documents more reliably); OCR only (cannot describe symbols); a paid vision API (no budget, D-15).
**Costs / revisit if:** a small model can invent items (it listed "ramps" for a sign that only showed a ramp symbol), so output is a lead with modest confidence; about 15 seconds per image on an 8 GB M1; two models cannot share the memory, so the text model and the vision model run one after the other. Revisit after upgrading Ollama (the `qwen2.5vl:3b` model is already downloaded) and on real posters and maps.
**Basis:** recorded (tested in this session; `src/atlas/extract/vision.py`, 3 tests; Ollama log of the crash).

### D-25: Fact extraction: rules propose, a small local model confirms, every fact keeps its verbatim quote (2026-11-16, accepted)
**Decision:** facts are found in crawled text in two stages. (1) `config/fact_rules.yaml` patterns propose a sentence for each of the 38 attributes, with a yes / limited / no guess from the words around it. (2) Optionally a small local model (`qwen2.5:3b` through Ollama, on the laptop) confirms or rejects each proposal and reads the other access-related sentences for facts the rules missed. The sentence is the quote, checked against the document; each fact records its method, extractor version, model and prompt version, and every model answer is cached by those plus the text.
**Why:** rules are free, instant and explainable; a model is needed for paraphrases and to reject headlines and program names, but a 3B model on an 8 GB laptop is slow and imperfect, so it only sees single sentences (cheap, short prompts, forced JSON). Quote-must-appear keeps invented text out. Versioned rows follow the history rule (D-17). The 261 facts read earlier by Claude serve as an automatic answer key, so quality can be measured without a person.
**Alternatives:** a larger model (does not fit the laptop alongside the crawler); a paid API (no budget, D-15); rules only (cannot read paraphrases: 74% recall of the answer key, with noise such as event titles).
**Costs / revisit if:** the answer key is itself model-read and unchecked by a person, so scores are a yardstick, not truth; a 3B model can mislabel values (kept as `confidence` 0.6 to 0.8, never 1); revisit when more memory, a lab GPU or a better small model is available, and after reading a sample of facts from government sites.
**Basis:** recorded (built and measured in this session: `src/atlas/extract/`, `scripts/eval_extraction.py`, `tests/test_extract.py`).

### D-24: "Report a problem" form with photo, stored in Supabase through one validating function (2026-11-16, accepted)
**Decision:** each place (map popup and details) and the map as a whole get a **Report a problem** button that opens a native dialog: five problem kinds, a short description, an optional photo (camera or device) and optional contact. The browser shrinks and re-encodes the photo (removing location data) and sends everything in one call to `submit_problem_report`, which validates, rate-limits per device, ignores a hidden honeypot field and stores the report and the photo in a locked table. The team reads a review view in the dashboard and exports photos with `scripts/export_reports.py` using the secret key. The button appears only when `report_ping()` answers, so the page never shows a form that cannot save.
**Why:** the user asked for a simple form with photo upload that the accessibility team will test, with the data really stored. One call with the existing public key reuses the proven rating pattern (locked table, function as the only door) and avoids Storage permission settings that could not be tested here; showing the button only when the backend is ready means publishing the page before running the SQL does no harm.
**Alternatives:** photos in Supabase Storage (better dashboard preview and no database growth, but needs bucket policies and an untested upload path with the new publishable key); a GitHub issue form (needs an account, no photo); email links (no storage).
**Costs / revisit if:** photos inside database rows grow the database (about 100 to 300 KB each; move to Storage beyond a few thousand); photos are viewed through an export script, not the dashboard; the SQL was parsed and cross-checked by tests but not run on the real project. Revisit after the team's test.
**Basis:** recorded (user request, 2026-11-16; `src/atlas/report_ui.py`, `supabase/problem_reports.sql`, 24 tests).

### D-23: Rules learned from the first government site (2026-11-15, accepted)
**Decision:** (1) Trap guards for depth and repeated folders apply to pages only, never to files (PDFs, Word, images): government sites keep files in deep folders. (2) Translated copies (pages under a language folder such as `/es/`) are skipped unless the crawl spec lists the language (`scope.languages`, default English). (3) The browser fallback is judged by signal strength: an app shell or collapsed sections always renders; a merely short page with scripts is rendered only until five tries on that host have added nothing. (4) A missing guessed path is "probe not found", never a failure. (5) Identical files under several addresses are one document. (6) A PDF the main reader crashes on is read by the fallback reader. (7) Icons and logos do not use the picture budget.
**Why:** the first crawl of odr.dc.gov skipped all 57 PDFs and 30 Word files, spent 23% of its budget on Spanish and Amharic copies, rendered 40 pages in the browser for nothing, and reported guessed paths as failures; each rule fixes one of these and was verified on the same site and with tests.
**Alternatives:** per-site hand-written rules (do not scale to the country); always rendering thin pages (slow and impolite); crawling translations (more pages, no new facts for our questions).
**Costs / revisit if:** skipping translations loses facts that only exist in a translated page (rare; set `languages` per site); the weak-signal guard may under-render a host whose first five thin pages happen to be empty (revisit with more sites).
**Basis:** recorded (crawl results and tests in this session).

### D-22: Reading tools: trafilatura, PyMuPDF and RapidOCR; heavier tools later (2026-11-15, accepted)
**Decision:** web pages are read with trafilatura (main text as markdown, so heading paths survive) with a simple fallback; tables, dates (htmldate) and structured data (extruct) are taken from the page; PDFs with PyMuPDF (text by page, tables), run in a separate process; scanned pages and images with RapidOCR. Docling and a local vision model are not used yet.
**Why:** all are free and install with pip on a laptop (the machine has no Tesseract and no GPU); trafilatura scored best in published extraction benchmarks and keeps headings, which later extraction needs to cite where a fact came from; RapidOCR read a test sign in under a second with 99% confidence; running PDFs in a separate process protects the crawler from malformed files.
**Alternatives:** Tesseract (needs a system install), PaddleOCR and Docling (large dependencies, better on tables and layouts), local vision models (slow on a laptop, kept for maps and posters where OCR alone is weak).
**Costs / revisit if:** OCR is weaker on photos of signs, maps and stylised posters; complex PDF tables need Docling; benchmark figures for the tools came from their own maintainers. Revisit after running on real government PDFs and posters (DC, Dayton).
**Basis:** recorded (built and tested in this session; tool claims from the crawler research, partly unchecked).

### D-21: Parameters set by the user's answers (2026-11-15, accepted)
**Decision:** (1) **Coverage is the whole city**, not selected places: a region such as Washington DC is collected completely, and Maryland starts from whole cities and counties. (2) **Outages and personal routes** are the predictions that matter most; missing-attribute filling and source reliability follow. (3) **Files are acceptable to the other team:** versioned Parquet plus a DuckDB file, monthly updates unless they ask otherwise. (4) **Everything runs on the user's computer for now** (no lab GPU assumed); Zenodo is the likely free home for raw archives; no WARC files for now. (5) Keep **all raw history** for the two target regions and thin old snapshots later. (6) **Scrapy first** with a custom fallback; crawler saves images and documents from **relevant pages only** at first. (7) Rating **tiers 80 / 50 / 30 accepted**; build the **calibration set** of about 100 facts from official data; **licensing:** facts and short quotes with links, full page copies private. (8) **Reddit is in scope** (changes my recommendation): needs research API access and strict handling. (9) **Mapillary street imagery is used if possible** (after a licence review: share-alike). (10) **User profile and feedback only after ethics review.**
**Why:** these are the user's own answers to the open questions; items 8 and 9 override my first recommendation (first release without them) because the user wants lived-experience data and imagery.
**Alternatives:** none: the user decided. Defaults used where the user left a question blank: skip and ask permission for sites whose terms forbid bots (C2); ask counsel before redistributing page-derived data (E3).
**Costs / revisit if:** laptop-only limits OCR and vision work (small batches, small models); Reddit needs approval and credentials and brings terms and privacy duties; Mapillary imagery is CC BY-SA, so derived data may carry share-alike duties; whole-city coverage raises crawl and storage needs. Revisit when a lab GPU or storage appears, and after the Reddit and Mapillary access steps.
**Basis:** recorded (`questions_for_you.md`, answers dated 2026-11-15).

### D-20: Build the crawler on Scrapy plus our own modules; decide after a spike (2026-11-15, proposed)
**Decision:** the web crawler uses Scrapy as the crawl engine (queue, politeness, retries, resume, sitemaps) with Playwright for JavaScript pages, and our own modules for what is specific to us: place-driven seeds, relevance scoring and budgets, completeness gates, provenance and extraction hand-off. A 2 to 3 day spike (phase C0) confirms it; if Scrapy cannot keep our priority queue, resume after a kill, and apply the same politeness limits to browser pages, we build a small custom async crawler instead. We crawl wide (save everything in scope) and extract deep (read only what looks relevant).
**Why:** the hard, easy-to-get-wrong parts of a polite, resumable crawler are already solved in Scrapy; our time is better spent on the parts nobody else builds. Saving everything in scope lets future questions be answered without re-crawling, and relevance steering keeps a country-wide crawl affordable at $0.
**Alternatives:** extend the current `web.py` (we would rewrite every hard part ourselves); Crawlee for Python (younger Python port); Crawl4AI (opinionated, adaptive mode but less control); Browsertrix Crawler (good WARC archiver, AGPL, Docker, weak custom logic: kept as an optional later add-on); fully custom (most control, most effort: the fallback).
**Costs / revisit if:** Scrapy's event loop and learning curve; the browser add-on's maintenance is unchecked; revisit after the spike and again if the add-on lags the Playwright version we need.
**Basis:** recorded (research and plan in `crawler_plan.md`, 2026-11-15); tool claims are mostly vendor-sourced and unchecked, which is why the spike comes first.
**Update 2026-11-15 (spike result):** Scrapy 2.20 handled all three spike conditions in tests on a local trap website: our priority scoring drives the queue (best-first under a small budget), a killed crawl resumes from the on-disk queue with no repeats, and the per-host politeness limits and Retry-After pauses apply to every request. Decision: **accepted, build on Scrapy.** **Update (C2):** Playwright pages now run inside the same pacing: the browser waits the same pause after any plain request to that host, loads one page at a time, and refuses requests to private addresses (tested).

### D-19: Schema v2 is added by an upgrade step; trust scores come from measured parts only (2026-11-15, accepted)
**Decision:** observation schema v2 (history, confidence, method, evidence) is produced by `schema.upgrade()` from the v1 tables the connectors already write, instead of changing every connector. Source ratings are computed by `trust.py` from components we can actually measure today (authority, provenance, freshness, completeness, quality); agreement and track record stay empty until fusion and reference data exist, and the remaining weights are rescaled. An unknown or unclear licence caps a source at tier B (usable, not redistributable).
**Why:** nothing breaks (80+ tests keep passing, existing data stays valid); we can reprocess old data into v2 and ship it. Counting unmeasured components as zero would unfairly sink every source, and counting them as full would invent evidence. Licence is a legal limit, not a quality score, so it caps the tier.
**Alternatives:** change all connectors to write v2 (bigger change, risky now); fill unmeasured components with a default (false precision).
**Costs / revisit if:** scores barely separate sources until agreement and track record exist (36 of 46 collected sources are tier A today); the weights are guesses. Revisit after the fusion step and the first reference-data comparison.
**Basis:** recorded (built and tested in this session: `src/atlas/schema.py`, `trust.py`, `cards.py`, `candidates.py`, `tests/test_phase0.py`).

### D-18: Question categories and source tracking live in code and update themselves (2026-11-15, accepted)
**Decision:** (1) `config/categories.yaml` is the single list of what wheelchair users ask about (trails, parking, restrooms, events, and so on), with the OSM selectors, Overture hints, attributes, page keywords, source kinds and refresh rates to fetch each; `docs/categories.md` is generated from it and checked against `config/attributes.yaml`. (2) Every `atlas fetch` appends a line to `data/ledger/fetch_log.jsonl` (source, region, time, ok or error) and refreshes `docs/source_inventory.md` and `data/source_inventory.csv`, which now include each source's URL and licence.
**Why:** the user wants the category list reused for later data fetching and wants the list of sources tracked without manual upkeep. Generated docs cannot drift from the config; the ledger is also the history needed in D-17.
**Alternatives:** a hand-written category doc and source list (drift, forgotten updates); a database table for the ledger (more moving parts for a small log).
**Costs / revisit if:** the inventory rewrites its whole table on each fetch (fine at this size); the OSM and Overture hints are a starting point and Overture names are unchecked.
**Basis:** recorded (user request, this session; `src/atlas/cli.py`, `src/atlas/inventory.py`, `scripts/make_categories_doc.py`).

### D-17: Keep history from day one (2026-11-15, proposed)
**Decision:** never overwrite data. Every observation carries `observed_at`, `valid_from`, `valid_to` and its source snapshot; a change adds a row. Archive real-time and fast-changing sources (GTFS-Realtime, weather, 311, key web pages) on a schedule, and keep every extraction run (model, prompt version, output).
**Why:** predictions (missing attributes, repair risk, outages, source reliability) and trends need what changed and when, and that history cannot be rebuilt later. Storing it costs little now.
**Alternatives:** keep only the latest value (smaller, but forecasting and "last confirmed" are impossible); archive only on demand (misses what we did not know we needed).
**Costs / revisit if:** more disk and a more careful schema; hourly feeds across many regions can grow fast, so thin or compress old snapshots if space runs out.
**Basis:** recorded (user request to plan for future computing and prediction, this session; `data_needs.md` section 3).

### D-16: Rate sources and facts automatically; no manual review (2026-11-15, proposed)
**Decision:** a trust engine scores each source (0 to 100: authority, provenance, freshness, completeness, internal quality, cross-source agreement, track record) and each fact (source score x extraction reliability x freshness x corroboration - conflicts). Sources are accepted automatically (Tier A, B), quarantined (C) or rejected (D). The assistant shows facts as confirmed, reported or unknown.
**Why:** the user cannot hand-check data, and manual review would not scale to a country. Showing the rating keeps the assistant honest instead of treating all sources as equally true.
**Alternatives:** human approval of every source (does not scale, no one to do it); no rating at all (all sources look equally reliable, unsafe); crowd voting on facts (needs many users).
**Costs / revisit if:** the rating measures consistency, not truth, so a confidently wrong source can pass; starting weights are guesses until reference data accumulates. Revisit after the first regions: compare scores against official data and the lab's wheelchair recordings, and tighten the thresholds.
**Basis:** recorded (user request, this session; `system_overview.md` section 4). The weights and cut-offs are my proposal: confirm.

### D-15: Zero-budget design: free tools, rules first, models last (2026-11-15, accepted)
**Decision:** plan and build everything to run at $0: no paid search, LLM, vision or hosting APIs. Use rules and filters first, small local open models only on pages that pass, free OCR and PDF parsers, Playwright for JavaScript pages, caching by content hash, and free hosts (Zenodo, Hugging Face, GitHub releases) for data releases.
**Why:** the user has no budget for now. A design that needs paid APIs would stall, and cheap-first processing also makes a national crawl feasible on modest hardware.
**Alternatives:** wait for funding (blocks progress); use frontier-model APIs on free credits (not reliable at national scale and credits run out).
**Costs / revisit if:** lower extraction accuracy than frontier models, slower processing, a smaller route D (search), files instead of a live API. Revisit when funding or university compute becomes available: first upgrade the claim-extraction model, then add a search API.
**Basis:** recorded (user instruction, this session; `national_data_plan.md` section 0.1). The specific free tools and their limits are unchecked: verify before relying on them.

### D-14: A source is complete only after independent checks pass (2026-11-15, proposed)
**Decision:** every crawl ends with six completeness gates (status audit, sitemap coverage, count check, archive check, keyword audit, sample audit); failures go to a gap queue and show in the coverage report. Pages needing JavaScript are fetched with a headless browser.
**Why:** the user wants to be sure we fetch every page we might need. A crawler cannot know what it missed unless it compares itself with something independent, and silent gaps would become silent wrong answers ("unknown" would be reported as "no").
**Alternatives:** crawl to a fixed depth and trust it (cheapest, but gaps are invisible); manual spot checks only (does not scale to a country).
**Costs / revisit if:** more requests and compute (archive lookups, headless browser, audits); tune the sample size and gate thresholds after the first two regions.
**Basis:** recorded (user request, this session; `national_data_plan.md` section 3.4).

### D-13: Diagrams as Mermaid text in the docs (2026-11-15, accepted)
**Decision:** system diagrams are written in Mermaid inside `docs/architecture.md` (green = exists, blue = planned), and every new design proposal comes with one.
**Why:** the user learns the system fastest from pictures. Mermaid renders in Obsidian and on GitHub, lives in git as text so diffs show what changed, and needs no drawing tool.
**Alternatives:** exported PNGs or slides (go stale, cannot be diffed), draw.io (separate files and tool).
**Costs / revisit if:** very large diagrams get hard to lay out; split them or use a drawing tool for posters and papers.
**Basis:** recorded (user request, this session).

### D-12: Discover sources automatically, then review (2026-11-15, proposed)
**Decision:** find new sources by automated discovery (open-data catalogs, `.gov` site crawl, place-driven pages, templated search), have an LLM draft the mapping, and approve each candidate by hand before it enters a release.
**Why:** the goal is the whole country, so hand-picking sites does not scale; but fully automatic ingestion would let wrong or unlicensed data into a dataset another team builds on.
**Alternatives:** hand-picked lists (what we did for Cincinnati and Oxford; does not scale); search-engine scraping per neighbourhood (the NYC predecessor; brittle, depends on one search engine, no provenance); fully automatic with no review (fast, but errors and licence problems reach the other team).
**Costs / revisit if:** needs a review queue and someone's weekly hours; revisit auto-approval once many mappings have been accepted without edits.
**Basis:** recorded (`national_data_plan.md`, sections 1 and 3).

### D-11: Repo name `accessibility-map`, no place name (2026-11-15, accepted)
**Decision:** rename `ohio-access-atlas` to `accessibility-map`; titles and docs describe Cincinnati and Oxford as current coverage, not the scope.
**Why:** the goal is national coverage, and "Ohio" and "Atlas" misdescribe the project. "Map" says what exists today; the assistant can grow under the same name.
**Alternatives:** `access-atlas` (smaller rename but still vague), `accessibility-assistant` (premature: the map is what exists), `accessible-places`.
**Costs / revisit if:** old Pages URLs stopped working (GitHub redirects the repo URL, not Pages). The Python package is still `atlas` and files still say `_atlas`; rename later only if worth the churn.
**Basis:** recorded (this session).

### D-10: Commits authored with the university email (2026-11-11, accepted)
**Decision:** all commits are `Mariam Zenaishvili <zenaism@miamioh.edu>`, with no AI co-author lines. History was rewritten on 2026-11-11 to enforce this. On 2026-11-15 we checked that GitHub links all 54 commits to the `zenaism` account and kept the miamioh email (rather than the private noreply address).
**Why:** the work is a Miami University research project and should be attributed to the researcher; the email is already linked to the account.
**Alternatives:** GitHub noreply address (keeps the university email out of public history; declined).
**Costs / revisit if:** the email is public in history; revisit if privacy matters more, but that means rewriting history and force-pushing again.
**Basis:** recorded (project memory, 2026-11-11 and 2026-11-15).

### D-09: Visitor ratings in Supabase, with only public keys in the repo (2026-11-12, accepted)
**Decision:** the map's one-tap accessibility ratings are stored in a Supabase project; the repo contains only the public URL and publishable key. Secret and `service_role` keys are never committed. The repo's `.gitleaks.toml` allows only `sb_publishable_` keys.
**Why:** the maps are static pages on GitHub Pages, so they have no server. Supabase gives a hosted database with row-level security reachable straight from the browser, with no server for us to run. A publishable key is safe to expose when row-level security limits what it can do.
**Alternatives:** running our own API (more to maintain), a form that creates GitHub issues (slow, needs a GitHub account), a spreadsheet backend (weak access control).
**Costs / revisit if:** depends on an external service and its free tier; abuse and spam need rate limits and moderation; ratings are crowd data and must stay labelled as such.
**Basis:** recorded (`config/ratings.yaml`, `supabase/ratings.sql`, project memory); the alternatives are inferred (confirm).

### D-08: Google Places and Yelp are live lookups and an evaluation check, not stored data (2026-11-11, accepted)
**Decision:** Google details are fetched in the browser when a place is selected, and only matched Place IDs are published. Google and Yelp are not part of the stored corpus.
**Why:** their terms do not allow keeping a permanent copy, so storing them would block us from sharing the dataset with the other lab team. They are still valuable as a comparison to measure how good our own data is.
**Alternatives:** store the details (breaks terms); leave Google out entirely (loses a useful comparison).
**Costs / revisit if:** the maps need a browser API key; it must be restricted to the site's HTTP referrer and never be a server key. Revisit if a research licence is granted.
**Basis:** recorded (`progress_log.md`, README).

### D-07: USGS The National Map as the only basemap (2026-11-12, accepted)
**Decision:** maps use the USGS basemap with the credit line USGS asks for.
**Why:** it is public domain. OpenStreetMap's volunteer tile servers do not allow this kind of use, and CARTO's free tiles now need a key.
**Alternatives:** OSM tiles (policy), CARTO (needs a key), Google tiles (terms, cost).
**Costs / revisit if:** less polished than commercial tiles. Revisit if we need a style that shows more detail at street level.
**Basis:** recorded (project memory; commit `8ef14da`).

### D-06: The map is GeoJSON files plus static pages (2026-11-11, accepted)
**Decision:** maps are generated GeoJSON and static HTML (Leaflet), committed to git and served by GitHub Pages; every place also gets a plain text page.
**Why:** no server to run or pay for; the data and the page always match; and the text pages work with screen readers, which matters for blind and wheelchair users.
**Alternatives:** a map server or vector tiles (too heavy for this size), a web framework (more to maintain).
**Costs / revisit if:** all data ships to the browser, so it will not scale to the whole country. For national scale the map should load per region or from vector tiles (see D-12 and the national plan).
**Basis:** recorded (`progress_log.md`: "Map: GeoJSON only for now"); the scaling note is inferred.

### D-05: DuckDB as the assistant's knowledge base (2026-11-12, accepted)
**Decision:** the assistant reads one DuckDB file (`data/kb/atlas.duckdb`) built from the published map data, with tables `places`, `facts` and `events`.
**Why:**
- *Right kind of questions.* "Nearest accessible restroom" needs a location filter and a distance sort, which vector search alone cannot do (recorded in `assistant_design.md`). DuckDB handles filters, joins and distance, and its spatial extension covers geometry.
- *Zero setup.* It is a single file that runs inside Python, with no database server to install or keep running, so a student can rebuild the whole thing with `make kb`.
- *Fits our data.* It reads Parquet and GeoJSON directly, matching how we store data (D-04).
- *Same data as the map.* Built from the map files, so the assistant answers from exactly what the map shows, and every fact keeps its quote and source.
**Alternatives:** PostgreSQL/PostGIS (stronger for many users writing at once, but needs a server and admin); SQLite/SpatiaLite (also single-file, but weaker for analytics and Parquet); a vector database only (cannot do distance and exact filters); a graph database (no clear gain for this data).
**Costs / revisit if:** one writer at a time and not built for many concurrent users. If the other team's app needs live multi-user queries, or the whole country makes the file very large, move serving to PostGIS (or a read-only API over DuckDB) while keeping DuckDB for analysis.
**Basis:** the "right kind of questions" reason is recorded (`assistant_design.md`, `src/atlas/assistant/kb.py`); the other reasons and the alternatives are inferred (confirm).

### D-04: Parquet and GeoParquet for stored data (2026-11-11, accepted)
**Decision:** processed data is Parquet (GeoParquet for geometry) in `data/processed/<region>/`; documents also as JSON Lines for the text index. The small map outputs stay as GeoJSON in git.
**Why:** compact, typed, and readable from Python, R, DuckDB and QGIS without our code, which matters because another team will use the data.
**Alternatives:** CSV (loses types and geometry), GeoJSON for everything (large, slow), a database dump (needs the same database).
**Costs / revisit if:** not human-readable in a text editor; GeoJSON exports remain for small layers.
**Basis:** recorded (`data_design.md`); reasons partly inferred (confirm).

### D-03: Entities plus observations, with provenance on every fact (2026-11-07, accepted)
**Decision:** everything is stored as entities (places, path segments, ramps, stops) and observations `(entity, attribute, value, signal, source, date, licence)`; website facts also keep a verbatim quote that is machine-checked against the source text.
**Why:** sources disagree (for example Metro codes 2,273 of 2,320 stops as "not possible" while other evidence conflicts), so we must keep every claim with its source instead of one merged value. It also lets us say "unknown" and "last confirmed in 2023", which is central to the research (RQ3 and RQ4).
**Alternatives:** one merged row per place (loses disagreement and provenance); free-text notes only (cannot be computed on).
**Costs / revisit if:** more rows and a merge step is needed to answer questions; the national plan extends the schema (v2) with confidence and evidence fields.
**Basis:** recorded (`study_design.md`, `data_design.md`, `progress_log.md`).

### D-02: Tool-using assistant, not plain RAG (2026-11-11, accepted)
**Decision:** structured questions go to query tools over DuckDB; open questions go to document retrieval; the model writes answers only from what the tools return, with sources.
**Why:** plain retrieval over text cannot do location filters or distance sorting, and an assistant that answers from memory could say "accessible" when it is not, which can strand someone (RQ4).
**Alternatives:** RAG over all text only; a fine-tuned model answering from memory.
**Costs / revisit if:** more engineering (tools, agent loop); needs an API key for the deployed model.
**Basis:** recorded (`assistant_design.md`).

### D-01: Regions are pinned to OSM boundary relations (2026-11-07, accepted)
**Decision:** each region is an OSM relation ID in `config/regions.yaml`, never matched by name.
**Why:** name matching picked the wrong place in the predecessor project ("Manhattan" matched Manhattan, Kansas).
**Alternatives:** name or geocoder lookup each time.
**Costs / revisit if:** adding a region needs one resolved ID; the national plan automates this step.
**Basis:** recorded (`config/regions.yaml` comment).
