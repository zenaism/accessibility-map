# Openway Assistant: work log (Track A)

Branch `feature/assistant`, worktree `accessibility-map-assistant`. Run started 2026-11-20 (overnight run, Mariam away).
Environment: `source env.sh` (untracked, sets PATH to the main checkout's `.venv`, `PYTHONPATH=src`, `ATLAS_*_DIR`).

## A0 Spikes

**Q1. Can `qwen2.5:3b` return valid plan JSON through Ollama's `format` (JSON schema) option?**
Yes for syntax: 6 of 6 test questions returned JSON that parses and matches the schema (enums obeyed).
No for meaning, with a bare prompt: the `intent` was right for only 2 of 6 questions (events and lending
questions came back as `restroom`; `need` was filled with `accessible_restroom` for unrelated questions;
free-text fields held made-up tokens such as `near_current_location`). So the schema guarantees shape,
not understanding. Consequence: model output is always validated and cross-checked, and the rules
planner is the default; the model planner gets few-shot examples and a "rules agree?" fallback (P2).

**Q2. Speed and memory (this 8 GB M1, nothing else heavy running).** 6.9 to 13.3 s per plan call
(first call 13.3 s includes loading the model; later calls 6.9 to 8.3 s), `num_ctx` 2048, temperature 0.
`ollama ps`: 2.3 GB, 100% GPU. Too slow for a "typing" feel, acceptable as an optional mode with a
visible "working" state. Model unloaded after the test (`ollama stop`).

**Q3. DuckDB full-text search?** Works here (`INSTALL fts; LOAD fts;` then `PRAGMA create_fts_index`,
`match_bm25` returned the expected row). Caveat: `INSTALL fts` fetches the extension the first time, so it
needs the network once. Not needed for v0: the existing keyword scoring in `search_places` is used and the
JavaScript guided mode cannot use DuckDB anyway. FTS is left as a documented option, not built.

**Verdict:** build everything with rules + templates as the floor (variant A) and the model as an optional,
validated helper (variants B to D).
