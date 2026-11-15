# Source catalog: researched candidate sources (Cincinnati and Oxford)

Roles: this file = reasoning per candidate source; `../SOURCES.md` = status (collected, next, idea); `resource_directory.md` = annotated organisations and platforms. Add a new source to `../SOURCES.md` first, and here only if it needs reasoning.

Status of each source in the pipeline is in `../SOURCES.md`; counts for collected data are in `source_inventory.md` (generated). This file holds the reasoning: what each source adds, how to access it, terms, priority.

Open data and official sites will make up most of the stored corpus. Google and Yelp terms do not let us keep a permanent copy, so they serve as live lookups and as an evaluation check. Facebook needs a researcher-access route rather than a scraper. Priority: **P1** = build first, **P2** = next, **P3** = if time allows.

## Places and amenities

| Source | What we take | Method | Terms and risk | Priority |
| --- | --- | --- | --- | --- |
| OpenStreetMap (already collected) | POIs with `wheelchair`, `toilets:wheelchair`, `changing_table`, entrances | Overpass (exists) | ODbL, store freely | P1 |
| [Overture Maps Places](https://docs.overturemaps.org/) | full POI list, names, categories, websites | GeoParquet download, bbox filter | CDLA-Permissive / ODbL, store freely | P1 |
| [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service) | `accessibilityOptions`: entrance, restroom, parking, seating | Nearby/Text Search per category, then Place Details | free monthly allowance per SKU since March 2025 (10,000 Essentials, 5,000 Pro, 1,000 Enterprise calls); we keep only `place_id` long-term, so it is a live tool plus evaluation snapshot | P2 |
| [Yelp](https://docs.developer.yelp.com/) | wheelchair attribute, review snippets | Yelp API (paid plans with a trial; you are checking access) or Apify Yelp actor | caching limits; store business id + attribute flags only, re-check terms | P2 |
| [Wheelmap / accessibility.cloud](https://www.accessibility.cloud/) | crowd ratings, partner datasets | API with free research key | per-dataset license | P2 |
| Changing Places / adult changing table maps | adult changing tables | page scrape or manual list | small, cite each | P2 |
| Venue access pages (museums, zoo, stadiums, theaters) | detailed access guides | fetch page or PDF, LLM extraction into the schema, human check | public pages, cite URL | P1 |

## Government and institutions

| Source | What we take | Method | Priority |
| --- | --- | --- | --- |
| [City of Cincinnati AccessCincy](https://www.cincinnati-oh.gov/manager/aging-and-accessibility/accesscincy/accesscincy-parks-and-recreation) and ADA office pages | accessible parks, trails, playgrounds, rec centers, accommodation contacts | crawl + extraction | P1 |
| Cincinnati Parks and Recreation Commission (incl. therapeutic recreation) | events, adaptive programs, facilities | calendar crawl | P1 |
| Great Parks of Hamilton County | accessible trails, paved loops, equipment, programs | crawl + extraction | P1 |
| Hamilton County Public Library and Lane Libraries (Oxford) | events, sensory programs, restrooms | event-calendar crawl | P1 |
| City of Oxford, Enjoy Oxford, Travel Butler County | parks, Uptown events, attractions | crawl | P1 |
| Miami University (Student Disability Services, campus maps, events calendar, museums) | accessible buildings and entrances, campus events | crawl, request accessibility map layer | P1 |
| Ohio DNR (Hueston Woods State Park) | accessible trails, cabins, fishing | crawl | P1 |
| Visit Cincy | accessibility guide, events | crawl | P1 |
| ADA transition plans (City, ODOT, Miami) | planned barrier fixes | PDF extraction | P2 |
| [Opportunities for Ohioans with Disabilities (OOD)](https://ood.ohio.gov/home) | state disability agency: vocational rehabilitation, College2Careers counselors at UC and Cincinnati State, Cincinnati office (895 Central Ave, to confirm), news bulletins | crawl as service records and documents; the homepage refused our automated fetch, so check by browser | P1 |

## Trails

| Source | What we take | Method | Priority |
| --- | --- | --- | --- |
| [Oxford Area Trails](https://www.oxfordareatrails.org/) | trail list, maps, surface notes | crawl + map-poster extraction | P1 |
| [Tri-State Trails](https://tristatetrails.org/trail/oxford-area-trails/) | regional trail network, paved trails | crawl, check for GIS download | P1 |
| [Midwestern Traveler](https://www.midwesterntraveler.com/oxfords-hiking-trails/) | first-hand trail descriptions | crawl as `document` | P2 |
| [Travel Butler County](https://www.travelbutlercounty.com/explore/oxford/sports-recreation) | recreation listings | crawl | P1 |
| [Cincinnati Museum Center trails page](https://www.cincymuseum.org/trails/) | trail program content (to confirm what this page holds) | crawl | P2 |
| [Cincinnati Parks Foundation hiking](https://www.cincinnatiparksfoundation.org/cprw-hiking) | park hikes, trail descriptions | crawl | P1 |
| [Cincinnati Nature Center](https://cincynature.org/visit-us/our-trails) | all-access Mashburn Discovery Trail, boardwalks | crawl | P1 |
| AllTrails | difficulty, length, "wheelchair friendly" and "paved" tags, reviews | no public API; ToS bans scraping, so manual lookup of a shortlist, store tags only | P3 |
| OSM trail geometry | line geometry, surface, width, incline | Overpass (extend existing query) | P1 |

**Trail map posters.** Many trail maps exist only as PDF or JPG posters. We will (1) download each image and record its URL and date. (2) A vision model extracts trail names, lengths, surfaces, blazes, trailheads, parking, restrooms and legend notes into JSON. (3) A second pass checks that every legend symbol and number was read. (4) Geometry comes from matching trail names to OSM ways. If no OSM match exists, we mark ground control points and georeference the poster in QGIS. (5) A person checks every trail record against the poster before it is published. Each record keeps `extraction_method = poster_ocr` and a confidence value.

## Community and lived experience

| Source | What we take | Method | Terms and risk | Priority |
| --- | --- | --- | --- | --- |
| Facebook groups and pages (city, neighborhood, disability, parent groups) | posts about accessible or blocked places | [Meta Content Library](https://transparency.meta.com/researchtools/meta-content-library) (the archive that replaced CrowdTangle in August 2024; covers public pages, groups and events). Apply through ICPSR's SOMAR enclave; needs IRB approval; you are checking access. Fallback: admin-approved export of public posts | Groups API removed April 2024; scraping breaks Meta terms; needs IRB review; store paraphrased claims only, no names | P2 |
| Reddit: city subs (r/cincinnati, r/MiamiOH, r/NorthernKentucky) searched for words like wheelchair, ramp, accessible, elevator, stairs; wheelchair subs (r/wheelchairs, r/disability, r/spinalcordinjuries) filtered to posts that mention Cincinnati or Oxford | posts and comments on access | existing connector (PRAW) | Reddit API terms; strip usernames | P1 |
| Google and Yelp reviews mentioning ramps, steps, restrooms | short claims | live API at query time only | no bulk storage | P3 |
| Blogs, local news (WCPO, Cincinnati Enquirer, CityBeat, Oxford Observer) | accessibility features, events | crawl articles as `document` | cite and link | P2 |

All community claims are stored as observations with `author_type = community`, linked to a place where we can match one. They rank below official and on-site evidence when they conflict.

## Wheelchair-specific sources

Disability-focused platforms have the most precise access details, such as door widths, roll-in showers and changing tables. They have few listings in Cincinnati and Oxford, though. So we use them to raise the confidence of places we already have, and we ask the larger ones for a research data partnership instead of scraping them. Local adaptive sports and disability groups are also a good source of events and of people who can check our answers.

## Access platforms and maps

| Source | What it adds | Access | Priority |
| --- | --- | --- | --- |
| [Wheel the World](https://wheeltheworld.com/) | verified hotel, tour and attraction access with measurements | crawl public listings for Ohio; email for a research data partnership | P1 |
| [Wheelmap / accessibility.cloud](https://www.accessibility.cloud/) | crowd ratings plus partner datasets | API with research key | P2 |
| [AccessNow](https://makerfairerome.eu/en/blog/the-apps-closing-the-accessibility-gap-in-travel/) | crowd-mapped places with detailed features (one source says more than 200 data points) | ask for partnership; app only otherwise | P2 |
| iAccess Life, WheelMate, AccessibleGO | reviews of restaurants, restrooms, parking, hotels | apps; check for any export or partnership | P3 |
| [Universal Changing Table Map](https://universalchangingtablemap.com) (Changing Spaces, Inspired Access Foundation) | adult changing tables with address, photo, table type | crawl map data for our area | P1 |
| [ODOT rest-area changing tables](https://news.yahoo.com/odot-adding-adult-sized-changing-100357713.html?fr=sycsrp_catchall) | adult tables at 28 renovated highway rest areas | crawl ODOT map | P2 |
| [TrailLink wheelchair-accessible trails](https://www.traillink.com/cityactivity/oxford-oh-wheelchair-accessible-trails/) | trails tagged wheelchair accessible, with surface and length (Oxford, Fairfield, Forest Park, Fort Thomas pages exist) | crawl city pages; check terms | P1 |
| [Project Sidewalk](https://sidewalk-cliffside-park.cs.washington.edu/v3/api-docs/cities) | CC0 crowd labels for curb ramps, obstacles, surface problems | Cities API; Columbus is deployed, Cincinnati and Oxford are not confirmed | P2 |
| Google Maps wheelchair routes, Moovit | accessible transit routing | link out at answer time only | P3 |

## Local guides and resource lists

| Source | What it adds | Priority |
| --- | --- | --- |
| [Visit Cincy accessibility guide](https://www.visitcincy.com/blog/post/accessiblity-in-the-cincinnati-region/) | ballpark, zoo (main paths accessible, Jungle Trails rough), riverboats, transit | P1 |
| [Cincinnati Museum Center accessibility sheet](https://www.cincymuseum.org/wp-content/uploads/2023/06/2023_CMC_CHM_Accessibility.pdf) | notes some ramps steeper than ADA recommends | P1 |
| [Cincinnati Art Museum accessibility guide (PDF)](https://cincinnatiartmuseum.org/media/qzypjozc/accessibility-guide-web.pdf) | entrances, loaner chairs, restrooms | P1 |
| [Cincinnati Children's travel resources](https://www.cincinnatichildrens.org/ongoing-support-resources/rest-recreation/vacations-travel) | Journeyable, Scootaround, accessible van rentals | P1 |
| [Accesstravel Cincinnati tour and Kings Island guide](https://accesstravel.com/es-ES/Story/Index/5403) | wheelchair-tested itineraries | P2 |
| Curb Free with Cory Lee, WheelchairTravel.org | travel blogs; no Cincinnati guide found yet | P3 |

## Adaptive sports and disability groups

| Group | What it offers | Priority |
| --- | --- | --- |
| [CRC Therapeutic Recreation](https://cincinnati-oh.gov/recreation/programs/therapeutic-recreation/adult-wheelchair-basketball) | adult wheelchair basketball (Cincinnati Royals, NWBA), [Miracle League baseball](https://cincinnati-oh.gov/recreation/programs/therapeutic-recreation/miracle-league-baseball) | P1 |
| [UC Adaptive Athletics](https://www.uc.edu/campus-life/accessibility-resources/uc-adaptive-athletics.html) | Ohio's first competitive collegiate adaptive program, events | P1 |
| [The Bridge Adaptive Sports and Recreation](https://activeproject.kellybrushfoundation.org/programs/the-bridge-adaptive-sports/) | adaptive sport and recreation programs in Greater Cincinnati | P1 |
| [Cincinnati Dragons](https://nkytribune.com/?p=292789) | youth wheelchair basketball | P2 |
| Stepping Stones, Center for Independent Living Options, Hamilton County DD Services | programs, events, possible partners to check our answers | P1 |

**Track chairs.** Found: MetroParks of Butler County lends two GRIT all-terrain chairs (adult and child), free with a refundable $75 deposit, picked up at Voice of America MetroPark and usable at any park. Before this, we had found no all-terrain chair loans near Cincinnati or Oxford. They exist at [Metroparks Toledo](https://metroparkstoledo.com/trackchair), Cleveland Metroparks and the Licking Park District. We will still ask Great Parks and Hueston Woods whether they lend chairs of their own, because "can I borrow one" is a likely question.

## Events, museums and trails

These are seed lists. The first crawl in Phase 1 checks each entry and adds what it finds. Where a site runs WordPress "The Events Calendar", we read its iCal feed (`?ical=1`) or `/wp-json/tribe/events/v1/events` instead of parsing HTML. [Cincy Jewfolk](https://cincyjewfolk.com/events/category/wheelchair-accessible/list/) and [Global Cincinnati](https://globalcincinnati.org/events-calendar/2026-02-25/?ical=1) already expose those feeds.

## Event sources

| Source | Region | Focus | Method |
| --- | --- | --- | --- |
| [Cincinnati Parks events calendar](https://www.cincinnati-oh.gov/cincyparks/visit-a-park/parks-events-calendar/disability-pride-month-adult-skate/) | Cincinnati | park events, including Disability Pride skate | HTML crawl |
| Cincinnati Recreation Commission, therapeutic recreation | Cincinnati | adaptive programs | HTML crawl |
| Great Parks of Hamilton County events | Cincinnati | nature programs | HTML / iCal |
| Visit Cincy events | Cincinnati | all city events | HTML crawl |
| [Blink Cincinnati](https://www.blinkcincinnati.com/resources/accessibility) | Cincinnati | light festival; access maps, viewing areas, access team | crawl + PDF maps |
| [Cincinnati Pride accessibility](https://www.cincinnatipride.org/accessibility) | Cincinnati | lift-equipped restroom, changing station | crawl |
| Disability Pride Cincy | Cincinnati | July disability pride events | crawl |
| Center for Independent Living Options (CILO) | Cincinnati | disability community events | crawl |
| Hamilton County DD Services | Cincinnati | events, programs | crawl |
| [ADA National Network calendar](https://adata.org/events-calendar/search) | both | ADA events, trainings | search by city |
| UC Accessibility Network | Cincinnati | digital accessibility conference, talks | crawl |
| [Cincy Jewfolk, wheelchair-accessible category](https://cincyjewfolk.com/events/category/wheelchair-accessible/list/) | Cincinnati | adapted sports at the Mayerson JCC, talks | iCal |
| [Sports 'N Spokes event list](https://sportsnspokes.com/event/2026-cincinnati-wheelchair-tennis-open/) | Cincinnati | wheelchair sports, e.g. Cincinnati Wheelchair Tennis Open | crawl |
| ArtsWave guide | Cincinnati | arts events across venues | crawl |
| Theaters: Playhouse in the Park, Cincinnati Shakespeare, Children's Theatre, Aronoff Center, Music Hall | Cincinnati | sensory-friendly and ASL shows, wheelchair seating | crawl |
| Hamilton County Public Library events | Cincinnati | sensory and inclusive programs | event-calendar crawl |
| CityBeat, Cincinnati.com, WCPO calendars | Cincinnati | general events | crawl, filter by venue access |
| Eventbrite, Meetup | both | community events | Eventbrite API by organizer or venue (no public search); Meetup GraphQL |
| [Enjoy Oxford events](https://enjoyoxford.org/events/) | Oxford | Uptown Music, Red Brick Fridays, OXtoberfest | crawl |
| Miami University events calendar, Performing Arts Series | Oxford | campus events, accessible seating | crawl / iCal |
| Lane Libraries events | Oxford | library programs | crawl |
| City of Oxford Parks and Recreation | Oxford | community events | crawl |
| Hueston Woods State Park events | Oxford | Maple Syrup Festival, nature programs | crawl |

Events expire. Each event row carries `expires_at = end + 1 day`, and a weekly job re-crawls every source. Disability-focused events are flagged `is_disability_focused = true`. General events stay in the corpus with whatever access features the page lists, so the assistant can answer "what can I do this weekend".

## Museums and cultural venues

| Venue | Region | Access page to fetch |
| --- | --- | --- |
| Cincinnati Museum Center (Natural History and Science, History Museum, Children's Museum, OMNIMAX, Holocaust and Humanity Center) | Cincinnati | [accessibility page](https://www.cincymuseum.org/accessibility) + [amenity PDF](https://www.cincymuseum.org/wp-content/uploads/2023/06/2023_CMC_CHM_Accessibility.pdf) |
| Cincinnati Art Museum | Cincinnati | [access page](https://cincinnatiartmuseum.org/access) |
| Taft Museum of Art (Sensory Inclusive certified) | Cincinnati | [visit page](https://taftmuseum.org/visit) |
| Contemporary Arts Center | Cincinnati | to find |
| National Underground Railroad Freedom Center | Cincinnati | to find |
| American Sign Museum | Cincinnati | to find |
| Cincinnati Fire Museum | Cincinnati | to find |
| William Howard Taft National Historic Site | Cincinnati | NPS accessibility page |
| Harriet Beecher Stowe House | Cincinnati | to find |
| Cincinnati Zoo and Botanical Garden, Krohn Conservatory | Cincinnati | to find |
| Cincinnati Observatory | Cincinnati | to find |
| Newport Aquarium, Behringer-Crawford Museum (KY, inside buffer) | Cincinnati | to find |
| Pyramid Hill Sculpture Park and Museum (Hamilton) | between | to find |
| Richard and Carole Cocks Art Museum (Miami) | Oxford | [Museums at Miami](https://miamioh.edu/museums-miami) |
| William H. McGuffey House and Museum | Oxford | [McGuffey Museum](https://miamioh.edu/cca/mcguffey-museum/index.html) |
| Robert A. Hefner Museum of Natural History (Upham Hall) | Oxford | Museums at Miami |
| Karl E. Limper Geology Museum (Shideler Hall) | Oxford | Museums at Miami |
| Doty Pioneer Farm Museum, Hueston Woods | Oxford | Travel Butler County, Ohio DNR |
| Smith Library of Regional History (Lane Libraries) | Oxford | to find |

For each venue we extract: step-free entrance and its location, elevators, accessible restrooms and changing tables, loaner wheelchairs, accessible parking, sensory hours, ASL and captioning, companion admission, and known problem areas.

## Trails (seed list)

| Trail or park | Region | Expected surface |
| --- | --- | --- |
| Little Miami Scenic Trail | Cincinnati | paved |
| Ohio River Trail and Smale Riverfront Park | Cincinnati | paved |
| Lunken Airport bike trail, Otto Armleder Park | Cincinnati | paved |
| Mill Creek Greenway | Cincinnati | paved, partial |
| Mt. Airy Forest, Everybody's Treehouse | Cincinnati | accessible ramp to treehouse; rest unpaved |
| Caldwell Preserve | Cincinnati | paved section |
| Winton Woods, Sharon Woods, Miami Whitewater Forest paved loops (Great Parks) | Cincinnati | paved |
| Cincinnati Nature Center, Mashburn Family Discovery Trail (0.72 mi, all-access) | Cincinnati | accessible |
| Ault Park, Eden Park | Cincinnati | paths, hills |
| Oxford Area Trails network | Oxford | mixed; poster extraction |
| Miami University Natural Areas | Oxford | mostly natural surface |
| Peffer Park, Oxford Community Park | Oxford | mixed |
| Hueston Woods State Park trails and lake paths | Oxford | mixed |


## Sources

Pages found through web search for this plan, as of 11 November 2026: [Blink accessibility](https://www.blinkcincinnati.com/resources/accessibility), [Enjoy Oxford events](https://enjoyoxford.org/events/), [Cincinnati Pride accessibility](https://www.cincinnatipride.org/accessibility), [Cincinnati Parks Disability Pride skate](https://www.cincinnati-oh.gov/cincyparks/visit-a-park/parks-events-calendar/disability-pride-month-adult-skate/), [Cincy Jewfolk accessible events](https://cincyjewfolk.com/events/category/wheelchair-accessible/list/), [Museums at Miami](https://miamioh.edu/museums-miami), [Cincinnati Art Museum access](https://cincinnatiartmuseum.org/access), [Cincinnati Nature Center trails](https://cincynature.org/visit-us/our-trails), [Meta v19 Graph API notes](https://developers.facebook.com/blog/post/2024/01/23/introducing-facebook-graph-and-marketing-api-v19/), [Google Places accessibility options](https://googleapis.dev/dotnet/Google.Maps.Places.V1/latest/api/Google.Maps.Places.V1.Place.Types.AccessibilityOptions.html), [Yelp API pricing report](https://appdevelopermagazine.com/yelp-fusion-api-outrageous-new-pricing/). I have not fetched these pages yet. Each one will be fetched and checked during Phase 1.
