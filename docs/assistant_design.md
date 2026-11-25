# Assistant design and question bank

_Attributes the questions rely on are defined in `data_landscape.md` section 1; question families for the national plan are in `national_data_plan.md` section 2. The bank below is the current Cincinnati/Oxford evaluation set._

## Assistant design

The assistant is a tool-using agent, not plain RAG. Questions like "nearest accessible restroom" need a location filter and a distance sort, which vector search cannot do. So structured questions go to query tools, and open questions go to document retrieval. Both return records with sources, and the model writes the answer only from what came back.

&#91;embedded content: atlas architecture · sources to answers\]

The model never answers from memory. It calls tools over the two stores, and the map file comes out of the same build.

**Stores.** DuckDB (with the spatial extension) holds places, trails, events and observations. A vector index (LanceDB or sqlite-vec) holds document chunks with metadata filters for region, category, entity id and date.

**Tools the agent can call**

| Tool | Inputs | Returns |
| --- | --- | --- |
| `locate` | address, landmark or "my location" | lat/lon, region |
| `find_places` | category, near, radius\_km, required access features, open\_now | ranked places with access summary, distance, sources |
| `find_events` | date range, region, keywords, disability\_focused | upcoming events with venue access |
| `find_trails` | region, max grade, surface, length range | trails with rating and trailhead amenities |
| `place_details` | place\_id | every observation, conflicts, documents, phone |
| `street_conditions` | point or two points | nearby curb ramps, steps, steep segments, open 311 issues, bus stops |
| `search_documents` | free text, optional entity or region filter | top chunks with URL and date |
| `live_check` | place\_id | current Google Places access flags and hours (not stored) |

**Answer rules**

- Every claim names its source and date. If a field is unknown, say so and suggest calling ahead, with the phone number.
- When sources disagree, say both and which is newer.
- Give distance and a plain note on the route (hills, steps, missing ramps) when the question is about getting somewhere.
- Never guess hours or event dates. Never say a place is "ADA compliant".
- **Short answers (B3):** one sentence of 25 words or fewer (an "I don't know" answer may use two short sentences within 25 words); a confidence line always; the nearest place confirmed by a recent source leads and closer old or unknown ones are noted; three follow-up chips; everything else is behind More. Enforced in `composer.py` and `composer.js` and tested in `tests/test_assistant_short_answers.py`. See D-83.

**Multimodal input.** Users can send a photo, for example an entrance, a flyer or a trail poster. A vision model reads it and passes the text and features to the same tools. Voice input can use the phone's speech-to-text.

**Model.** One capable model runs the agent loop, and a smaller, cheaper model does bulk extraction in the pipeline. A Claude Pro plan covers claude.ai and Claude Code, so during development Claude Code can do the extraction and poster reading inside the subscription. The deployed assistant calls the Claude API, which is billed separately. Planned: Claude Opus 5.5 for the agent and Claude Haiku 5.5 for bulk extraction.

**Evaluation.** The question bank below becomes a test set with expected answers. We measure: whether the right records were retrieved (recall at 5), whether each claim is supported by a cited record (checked by a second model and by hand on a sample), whether it says "unknown" when it should, and how often the cited source is correct.

## Question bank

These are questions in the words a wheelchair user or companion might type. They will be stored in `eval/questions.yaml` with a category, the tools we expect the agent to use, and an expected answer once data exists. We will add real questions from users as we get them.

**Restrooms**

- Where's the closest wheelchair accessible bathroom to me right now?
- Is there a bathroom with an adult changing table anywhere downtown?
- Does Findlay Market have an accessible restroom?
- I'm at Smale Park. Where can I use the bathroom?
- Are there accessible restrooms in Uptown Oxford open after 9 pm?

**Food and drink**

- Find me a coffee shop in OTR with no steps at the door.
- Which restaurants in Oxford have an accessible bathroom too?
- Is there a brewery with a ramp and outdoor seating near Northside?
- Can I get my power chair into Skyline on Ludlow?
- Somewhere for a birthday dinner for 8, one person uses a wheelchair, Over-the-Rhine.

**Getting there**

- Is the sidewalk from Union Terminal to the bus stop OK for a wheelchair?
- Is Mt. Adams too steep to roll around?
- Which bus goes from downtown to the zoo and can I get on it with my chair?
- Where's accessible parking near Great American Ball Park?
- Are there curb ramps on High Street in Oxford?
- Any sidewalk closures or construction near Fountain Square this week?
- How do I sign up for Metro Access paratransit?

**Outdoors and trails**

- What are some paved trails near Cincinnati I can do in a wheelchair?
- Is any trail in Oxford flat enough for a manual chair?
- How long is the paved loop at Sharon Woods and is there a bathroom at the start?
- Where can I see a waterfall without stairs?
- Is Everybody's Treehouse really wheelchair accessible?
- Is Hueston Woods good for someone in a wheelchair? Which parts?
- Can I borrow an all-terrain wheelchair at any park around here?

**Museums and culture**

- Which museums in Cincinnati are fully wheelchair accessible?
- Does the Art Museum lend wheelchairs?
- Is the McGuffey Museum accessible or is it all stairs?
- Are there sensory-friendly hours at any museum this month?
- Can I get wheelchair seats for a show at the Aronoff, and how much is a companion ticket?

**Events**

- What accessibility events are happening in Cincinnati this month?
- Anything fun to do this weekend in Oxford that's wheelchair friendly?
- When is Disability Pride Cincinnati this year?
- Is Blink accessible? Where are the viewing areas for wheelchairs?
- Are there adaptive sports leagues I can join, like wheelchair basketball?
- Any support groups for new wheelchair users in Cincinnati?

**Services and help**

- Where can I get my wheelchair fixed in Cincinnati?
- Who do I call to report a broken curb ramp?
- Which hotels in Oxford have roll-in showers?
- I'm visiting Miami University. Which buildings have accessible entrances and where?
- Where can I rent a wheelchair-accessible van?

**Trust and unknowns (the system should handle these carefully)**

- Is this info up to date?
- People on Facebook said the ramp at X is broken. Is that true?
- Why does Google say it's accessible but you say unknown?
- Is X ADA compliant?

