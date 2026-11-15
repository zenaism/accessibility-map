# Study design: method and threats to validity

The research questions, paper plan, venues and timeline live in [`research_questions.md`](research_questions.md) (revised after the literature review). This file keeps only the method and the threats to validity.

## Method
1. **Collect** (`atlas fetch`): every source becomes rows of
   `(entity, attribute, value, signal, provenance)`. Raw responses are cached for reproducibility.
2. **Conflate**: link records about the same real-world object across sources using spatial
   tolerance plus type compatibility (e.g. CAGIS ramp ↔ OSM kerb within 10 m). Report sensitivity
   to the tolerance (5/10/20 m).
3. **Ground truth**: stratified random sample (by source, neighbourhood, and signal) of about 200
   ramps, segments and entrances; two auditors; report Cohen's κ.
4. **Derive**: slope from DEM per segment; segment-level accessibility under different user
   profiles (manual vs. power chair; max incline from user profiles).
5. **Benchmark**: generate questions from templates plus LLM paraphrase. The answer comes *from the
   data*, with evidence rows attached. Include unanswerable questions (no data) on purpose.
   Hold out Oxford, or held-out neighbourhoods, for a generalisation test.
6. **Model**: (a) RAG over observations, (b) small model (1 to 4 B) fine-tuned on QA, (c) frontier
   LLM zero-shot. Metrics: accuracy, evidence faithfulness, abstention F1, latency on device.

## Threats to validity (address before reviewers do)
- Coded fields can be misleading: Metro marks about 96% of stops `wheelchair_boarding=2`. Confirm
  semantics with SORTA before using.
- City GIS has geometry but almost no condition data (`ASSETCONDITION` filled on 1 of 833k).
  Presence ≠ usability.
- 311 reflects who reports, not where the barriers are (reporting bias by neighbourhood/income).
  Normalise per capita and discuss.
- Temporal drift: record retrieval dates; ramps get rebuilt and feeds change.
- Rule-based signals are heuristics; validate them against the field audit.
