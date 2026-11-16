# Question categories

_Generated from `config/categories.yaml` by `scripts/make_categories_doc.py`. Do not edit by hand: change the YAML and rerun._

Everything a wheelchair user might ask about, grouped so that data fetching, source discovery and evaluation all use the same list. For each category the YAML holds the OpenStreetMap selectors, Overture category hints, the attributes to extract, the words that mark a relevant web page, the usual source kinds (letters A to K in `source_types.md`), how often to refresh, and whether values expire. Attribute meanings are in `config/attributes.yaml` (existing) and under *new attributes* below (to add).

Status: **have** = collected for Cincinnati and Oxford, **partial** = some, **none** = not yet. Priority: P0 first regions, P1 next, P2 later.

## Overview

| Priority | Category | Kind | Refresh | Expires | Status |
|---|---|---|---|---|---|
| P0 | [Museums, theaters, libraries and attractions](#culture_entertainment) | place | 180 days | no | have |
| P0 | [Events and activities nearby](#events) | event | 7 days | yes | have |
| P0 | [Restaurants, cafes and bars](#food_drink) | place | 180 days | no | partial |
| P0 | [Accessible parking and drop-off](#parking_dropoff) | place | 180 days | no | partial |
| P0 | [Parks, gardens, playgrounds and nature areas](#parks_outdoors) | place | 180 days | no | partial |
| P0 | [Restrooms and changing tables](#restrooms) | place | 90 days | no | have |
| P0 | [Sidewalks, ramps, crossings and slope](#street_network) | infrastructure | 90 days | no | have |
| P0 | [Accessible trails and hiking routes](#trails_hiking) | route | 180 days | no | partial |
| P0 | [Transit and getting around](#transit_mobility) | infrastructure | 1 days | yes | partial |
| P1 | [Adaptive sports and recreation](#adaptive_sports_recreation) | service | 90 days | no | partial |
| P1 | [Campuses and schools](#education_campus) | place | 180 days | no | partial |
| P1 | [Hospitals, clinics and care](#health_care) | place | 180 days | no | partial |
| P1 | [What people report (cross-cutting, low confidence)](#lived_experience) | information | 90 days | no | none |
| P1 | [Hotels and places to stay](#lodging) | place | 180 days | no | none |
| P1 | [Equipment, repair and rental](#mobility_equipment_services) | service | 180 days | no | partial |
| P1 | [Hearing, vision and cognitive access (cross-cutting)](#sensory_communication) | information | 180 days | no | partial |
| P1 | [Shopping and daily services](#shopping_daily_services) | place | 180 days | no | partial |
| P1 | [Stadiums and arenas (watching sport)](#sports_venues) | place | 180 days | no | partial |
| P1 | [Support services, rights and reporting](#support_rights) | information | 180 days | no | partial |
| P1 | [Closures, construction, snow and outages](#temporary_conditions) | condition | 1 days | yes | partial |
| P1 | [Accessible travel and itineraries](#tourism_itineraries) | information | 180 days | no | partial |
| P2 | [Government, voting and civic services](#civic_government) | place | 180 days | no | none |
| P2 | [Rest, shade, lighting and noise](#comfort_environment) | condition | 365 days | no | none |
| P2 | [Emergencies, shelters and safety](#emergency_safety) | information | 30 days | yes | none |
| P2 | [Accessible housing](#housing) | information | 365 days | no | none |
| P2 | [Places of worship and community centers](#worship_community) | place | 365 days | no | none |

Kinds: place | route | event | service | infrastructure | condition | information.

## culture_entertainment

**Museums, theaters, libraries and attractions** (priority P0, status have)

Typical questions:
- Can I get around the whole museum? Are wheelchairs lent?
- Where do wheelchair users sit in the theater? Is there companion seating?

- **Attributes to extract:** entrance_step_free, accessible_route_inside, elevator, wheelchair_loan, scooter_or_ecv, accessible_seating, companion_admission, sensory_friendly, quiet_room, restroom_accessible, accessibility_map, accessibility_contact, ramp_steep
- **OSM selectors:** `nwr["tourism"~"^(museum|gallery|attraction|zoo|aquarium|theme_park|artwork)$"]`; `nwr["amenity"~"^(theatre|cinema|library|arts_centre|community_centre)$"]`; `nwr["historic"]`
- **Overture hints (unchecked):** museum, art_gallery, theater, movie_theater, library, zoo, aquarium, landmark_and_historical_building
- **Page words:** accessibility, accessible, plan your visit, visitor guide, wheelchair, sensory, accessibility guide, access guide
- **Source kinds:** C, D

## events

**Events and activities nearby** (priority P0, status have)

Typical questions:
- What is happening near me this weekend that I can get into?
- Is there ASL, audio description, captions, sensory-friendly hours?
- Is the event venue step-free, and where do wheelchair users sit?

- **Attributes to extract:** accessible_seating, sensory_friendly, asl_interpretation, captioning, audio_description, assistive_listening, companion_admission, accessible_parking, notice
- **OSM selectors:** none (not map-based)
- **Overture hints (unchecked):** event_space, performing_arts
- **Page words:** event, events calendar, accessibility, ASL, wheelchair seating, sensory friendly, audio described, relaxed performance, request accommodation
- **Source kinds:** C, F, D

## food_drink

**Restaurants, cafes and bars** (priority P0, status partial)

Typical questions:
- Which restaurants have a step-free entrance and an accessible restroom?
- Are the tables and counters at a usable height?

- **Attributes to extract:** entrance_step_free, automatic_door, restroom_accessible, accessible_parking, seating_rest, braille, large_print
- **OSM selectors:** `nwr["amenity"~"^(restaurant|cafe|bar|pub|fast_food|ice_cream|biergarten)$"]`
- **Overture hints (unchecked):** restaurant, cafe, bar, fast_food_restaurant, bakery
- **Page words:** wheelchair accessible, accessibility, accessible entrance, ramp, step-free, restroom, parking, patio
- **Source kinds:** A, C, B

## parking_dropoff

**Accessible parking and drop-off** (priority P0, status partial)

Typical questions:
- Where can I park close to the entrance, with room for a ramp van?
- Is there accessible parking at this venue, how many, what does it cost?
- Where do I get dropped off?

- **Attributes to extract:** accessible_parking, drop_off, transit_access
- **OSM selectors:** `nwr["amenity"="parking"]`; `nwr["parking_space"="disabled"]`; `nwr["capacity:disabled"]`
- **Overture hints (unchecked):** parking
- **Page words:** accessible parking, handicap parking, disabled parking, van accessible, ADA parking, drop-off, valet, garage clearance, parking map
- **Source kinds:** A, C, D, K

## parks_outdoors

**Parks, gardens, playgrounds and nature areas** (priority P0, status partial)

Typical questions:
- Which parks have accessible paths, restrooms and picnic tables?
- Is there an accessible playground, kayak launch or fishing pier?

- **Attributes to extract:** entrance_step_free, accessible_route_inside, accessible_parking, restroom_accessible, seating_rest, adaptive_recreation, accessible_lodging, all_terrain_chair
- **OSM selectors:** `nwr["leisure"~"^(park|nature_reserve|garden|playground|dog_park|fishing|picnic_table)$"]["name"]`; `nwr["boundary"="protected_area"]["name"]`
- **Overture hints (unchecked):** park, playground, garden, campground, beach
- **Page words:** accessible park, accessibility, playground, picnic, shelter, kayak launch, fishing pier, campground, accessible campsite
- **Source kinds:** A, C, D

## restrooms

**Restrooms and changing tables** (priority P0, status have)

Typical questions:
- Where is the nearest accessible restroom?
- Is there an adult changing table?
- Is it open now, is it free?

- **Attributes to extract:** restroom_accessible, restroom_family, adult_changing_table, entrance_step_free, notice
- **OSM selectors:** `nwr["amenity"="toilets"]`; `nwr["changing_table"]`
- **Overture hints (unchecked):** public_toilet
- **Page words:** accessible restroom, accessible toilet, adult changing table, changing places, family restroom, companion restroom, restroom hours
- **Source kinds:** A, B, C

## street_network

**Sidewalks, ramps, crossings and slope** (priority P0, status have)

Typical questions:
- Is there a step-free route from A to B?
- How steep is this street? Is there a curb ramp at the crossing?
- Is there an audible signal, is the sidewalk blocked?

- **Attributes to extract:** ramp_steep
- **OSM selectors:** `way["highway"~"^(footway|path|pedestrian|steps|cycleway)$"]`; `node["kerb"]`; `nwr["crossing"]`; `node["highway"="traffic_signals"]`
- **Overture hints (unchecked):** none
- **Page words:** sidewalk, curb ramp, crosswalk, pedestrian signal, accessible route, transition plan, ADA inventory
- **Source kinds:** A, B, G, I

## trails_hiking

**Accessible trails and hiking routes** (priority P0, status partial)

Typical questions:
- Is there a paved or hard-packed trail near me?
- How steep is it, how wide, what surface?
- Is there accessible parking and a restroom at the trailhead?
- Can I borrow an all-terrain (track) chair?

- **Attributes to extract:** trail_surface, trail_width, trail_grade, accessible_parking, restroom_accessible, seating_rest, all_terrain_chair, mobility_device_policy, notice
- **OSM selectors:** `way["highway"~"^(path|footway|cycleway|track|bridleway)$"]["name"]`; `relation["route"~"^(hiking|foot|bicycle|walking)$"]`; `nwr["tourism"="viewpoint"]`
- **Overture hints (unchecked):** park, hiking_trail, nature_reserve
- **Page words:** accessible trail, wheelchair accessible trail, paved trail, ADA trail, universal access, all-terrain chair, track chair, grade, surface, trailhead
- **Source kinds:** A, C, D, K

## transit_mobility

**Transit and getting around** (priority P0, status partial)

Typical questions:
- Is this bus stop accessible? Does the bus have a ramp?
- Is the elevator at the station working today?
- How do I use paratransit, am I eligible, how do I book?
- Is there a wheelchair-accessible taxi or rideshare?

- **Attributes to extract:** transit_access, accessible_parking, drop_off, notice
- **OSM selectors:** `nwr["highway"="bus_stop"]`; `nwr["public_transport"~"^(platform|stop_position|station)$"]`; `nwr["railway"~"^(station|halt|tram_stop|subway_entrance)$"]`; `nwr["amenity"~"^(taxi|bus_station|ferry_terminal)$"]`
- **Overture hints (unchecked):** bus_station, train_station, airport, taxi_service, transit_station
- **Page words:** paratransit, ADA paratransit, accessible service, elevator outage, wheelchair, ramp, lift, eligibility, how to ride
- **Source kinds:** A, G, B

## adaptive_sports_recreation

**Adaptive sports and recreation** (priority P1, status partial)

Typical questions:
- Where can I play wheelchair basketball, swim, ski or kayak?
- Who lends adaptive equipment?

- **Attributes to extract:** adaptive_recreation, entrance_step_free, restroom_accessible, accessible_parking, companion_admission
- **OSM selectors:** `nwr["leisure"~"^(sports_centre|swimming_pool|fitness_centre|pitch|golf_course)$"]`
- **Overture hints (unchecked):** sports_and_recreation, gym, swimming_pool
- **Page words:** adaptive sports, adaptive recreation, wheelchair basketball, adaptive, para, therapeutic recreation, accessible equipment, pool lift
- **Source kinds:** C, K, F

## education_campus

**Campuses and schools** (priority P1, status partial)

Typical questions:
- Which campus buildings and routes are accessible?
- Where is disability services, where is accessible parking?

- **Attributes to extract:** entrance_step_free, elevator, accessible_parking, accessibility_map, accessibility_contact, transit_access
- **OSM selectors:** `nwr["amenity"~"^(university|college|school)$"]`; `nwr["building"~"^(university|college|school|dormitory)$"]`
- **Overture hints (unchecked):** university, college, school
- **Page words:** disability services, accessibility, accessible entrance map, parking map, building access, accommodations
- **Source kinds:** C, D, K

## health_care

**Hospitals, clinics and care** (priority P1, status partial)

Typical questions:
- Is this clinic wheelchair accessible, are exam tables adjustable?
- Where is the accessible entrance and parking at the hospital?

- **Attributes to extract:** entrance_step_free, accessible_route_inside, elevator, accessible_parking, drop_off, restroom_accessible, wheelchair_loan, accessibility_contact, asl_interpretation
- **OSM selectors:** `nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy)$"]`; `nwr["healthcare"]`
- **Overture hints (unchecked):** hospital, clinic, doctor, dentist, physical_therapy
- **Page words:** accessibility, patient accessibility, accessible exam, wheelchair, interpreter, parking, entrances, visitor information
- **Source kinds:** C, A

## lived_experience

**What people report (cross-cutting, low confidence)** (priority P1, status none)

Typical questions:
- What is it really like, what do other wheelchair users say?

- **Attributes to extract:** listed_accessible
- **OSM selectors:** none (not map-based)
- **Overture hints (unchecked):** none
- **Page words:** my experience, wheelchair, accessible, not accessible, review, tip
- **Source kinds:** E, B

## lodging

**Hotels and places to stay** (priority P1, status none)

Typical questions:
- Is there a roll-in shower? How many accessible rooms?
- Is the pool accessible?

- **Attributes to extract:** accessible_lodging, entrance_step_free, elevator, accessible_parking, restroom_accessible, wheelchair_loan
- **OSM selectors:** `nwr["tourism"~"^(hotel|motel|hostel|guest_house|apartment|camp_site)$"]`
- **Overture hints (unchecked):** hotel, motel, bed_and_breakfast, campground
- **Page words:** accessible room, roll-in shower, ADA room, accessibility, mobility accessible, bed height
- **Source kinds:** C, B

## mobility_equipment_services

**Equipment, repair and rental** (priority P1, status partial)

Typical questions:
- Who repairs wheelchairs, rents a scooter or an accessible van?
- Where can I borrow equipment?

- **Attributes to extract:** mobility_service, wheelchair_loan, all_terrain_chair, adaptive_recreation
- **OSM selectors:** `nwr["shop"~"^(medical_supply|mobility)$"]`; `nwr["healthcare"="medical_supply"]`
- **Overture hints (unchecked):** medical_supply, durable_medical_equipment
- **Page words:** wheelchair repair, mobility equipment, durable medical equipment, loan closet, accessible van, ramp, lift
- **Source kinds:** C, K

## sensory_communication

**Hearing, vision and cognitive access (cross-cutting)** (priority P1, status partial)

Typical questions:
- Is there ASL, captioning, audio description, braille, large print?
- Is there a quiet room or a sensory-friendly time?

- **Attributes to extract:** asl_interpretation, captioning, assistive_listening, audio_description, braille, large_print, tactile, sensory_friendly, quiet_room, service_animals
- **OSM selectors:** none (not map-based)
- **Overture hints (unchecked):** none
- **Page words:** ASL, interpreter, captioning, audio description, assistive listening, braille, large print, tactile, sensory friendly, service animals
- **Source kinds:** C, D, F

## shopping_daily_services

**Shopping and daily services** (priority P1, status partial)

Typical questions:
- Which grocery stores, pharmacies and banks are step-free?
- Is there a motorized cart, an accessible checkout?

- **Attributes to extract:** entrance_step_free, automatic_door, scooter_or_ecv, accessible_parking, restroom_accessible
- **OSM selectors:** `nwr["shop"~"^(supermarket|convenience|mall|department_store|chemist|clothes)$"]`; `nwr["amenity"~"^(bank|post_office|pharmacy|atm)$"]`
- **Overture hints (unchecked):** grocery_store, supermarket, shopping_center, pharmacy, bank, post_office
- **Page words:** accessibility, accessible, motorized cart, wheelchair, ADA, store services
- **Source kinds:** A, C

## sports_venues

**Stadiums and arenas (watching sport)** (priority P1, status partial)

Typical questions:
- Where are wheelchair seats, how do I book, is there companion seating?

- **Attributes to extract:** accessible_seating, companion_admission, entrance_step_free, accessible_parking, elevator, restroom_accessible, accessibility_map
- **OSM selectors:** `nwr["leisure"~"^(stadium|sports_centre)$"]`
- **Overture hints (unchecked):** stadium_arena, sports_venue
- **Page words:** accessible seating, ADA seating, wheelchair seating, accessibility guest services, accessible entrance
- **Source kinds:** C, D

## support_rights

**Support services, rights and reporting** (priority P1, status partial)

Typical questions:
- Who do I call to report a broken ramp or request a curb ramp?
- What are my rights, how do I file an ADA complaint?
- Where is the independent living center, what benefits exist?

- **Attributes to extract:** accessibility_contact
- **OSM selectors:** `nwr["office"="association"]["social_facility"]`; `nwr["amenity"="social_facility"]`
- **Overture hints (unchecked):** social_service_organization, nonprofit_organization
- **Page words:** ADA coordinator, report a problem, curb ramp request, 311, complaint, independent living, disability services, benefits, 211
- **Source kinds:** C, B, K, I

## temporary_conditions

**Closures, construction, snow and outages** (priority P1, status partial)

Typical questions:
- Is the route, elevator or entrance blocked today?
- Is the trail closed after the storm, is the sidewalk icy?

- **Attributes to extract:** notice
- **OSM selectors:** none (not map-based)
- **Overture hints (unchecked):** none
- **Page words:** closure, closed, construction, detour, outage, out of service, icy, flooded, alert, notice
- **Source kinds:** G, A, F

## tourism_itineraries

**Accessible travel and itineraries** (priority P1, status partial)

Typical questions:
- What can I do in this city in a weekend with a wheelchair?
- Is there an accessible tour, a wheelchair-friendly itinerary?

- **Attributes to extract:** accessibility_map, accessibility_contact, wheelchair_loan
- **OSM selectors:** `nwr["tourism"~"^(information|attraction|viewpoint)$"]`
- **Overture hints (unchecked):** tourist_attraction, visitor_center, tour_operator
- **Page words:** accessible travel, accessibility guide, wheelchair-friendly, itinerary, visitor guide, accessible tour
- **Source kinds:** C, E

## civic_government

**Government, voting and civic services** (priority P2, status none)

Typical questions:
- Is my polling place accessible?
- Is city hall, the courthouse or the DMV step-free?

- **Attributes to extract:** entrance_step_free, automatic_door, elevator, accessible_parking, accessibility_contact, asl_interpretation
- **OSM selectors:** `nwr["amenity"~"^(townhall|courthouse|police|fire_station|polling_station)$"]`; `nwr["office"="government"]`
- **Overture hints (unchecked):** city_hall, courthouse, government_office, post_office
- **Page words:** accessibility, ADA, polling place, accommodations, accessible entrance
- **Source kinds:** C, A, I

## comfort_environment

**Rest, shade, lighting and noise** (priority P2, status none)

Typical questions:
- Are there benches and shade along this route?
- Is the route lit at night, is the place loud or crowded?

- **Attributes to extract:** seating_rest, quiet_room, sensory_friendly
- **OSM selectors:** `node["amenity"="bench"]`; `node["highway"="street_lamp"]`; `nwr["amenity"="shelter"]`
- **Overture hints (unchecked):** none
- **Page words:** shade, benches, rest area, lighting, quiet hours, crowded, noise level
- **Source kinds:** A, B, E

## emergency_safety

**Emergencies, shelters and safety** (priority P2, status none)

Typical questions:
- Where is an accessible cooling or warming center or shelter?
- How do I get emergency alerts, how do I evacuate with a wheelchair?

- **Attributes to extract:** entrance_step_free, accessible_parking, restroom_accessible, notice
- **OSM selectors:** `nwr["emergency"~"^(assembly_point|shelter)$"]`; `nwr["amenity"~"^(shelter|hospital)$"]`
- **Overture hints (unchecked):** emergency_service
- **Page words:** cooling center, warming center, shelter, evacuation, emergency preparedness, people with disabilities, accessible shelter
- **Source kinds:** C, G

## housing

**Accessible housing** (priority P2, status none)

Typical questions:
- Where are accessible apartments, what are the rules for modifications?

- **Attributes to extract:** entrance_step_free, elevator, accessible_parking
- **OSM selectors:** `nwr["building"~"^(apartments|residential)$"]["wheelchair"]`
- **Overture hints (unchecked):** apartment, housing_authority
- **Page words:** accessible apartment, accessible unit, housing authority, reasonable accommodation, home modification
- **Source kinds:** C, K

## worship_community

**Places of worship and community centers** (priority P2, status none)

Typical questions:
- Is the church or community center step-free, with accessible seating?

- **Attributes to extract:** entrance_step_free, accessible_route_inside, restroom_accessible, accessible_parking, accessible_seating
- **OSM selectors:** `nwr["amenity"~"^(place_of_worship|community_centre|social_facility)$"]`
- **Overture hints (unchecked):** place_of_worship, community_center
- **Page words:** accessibility, accessible entrance, wheelchair, ramp, hearing loop
- **Source kinds:** C
