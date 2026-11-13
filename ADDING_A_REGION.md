# Adding a venue, or a new region (city)

## Just adding a venue to an existing region?

You need four things, then you're done (the venue page and map links pick it up
automatically):

1. **A scraper**, `scrapers/<region>/<venue>.py` — write it as described in
   [section 2](#2-per-venue-scraper) below, and check it with
   `python main.py --env dev --venues "<Venue Name>" --no-summary` once it is
   registered.
   **Have it fill `description` for every event** (a sentence or two, with the artists' names; see
   [2b-ii](#2b-ii-descriptions)): the search box reads descriptions, so a show with none can only be
   found by its title.
2. **A registry entry** in `main.py`: import the module and add
   `"<Venue Name>": <module>.<scrape_function>` to that region's block in
   `get_venue_scrapers()` (section 1e).
3. **An address** in `docs/data/<region>_venues.json`, under the exact `venue`
   string the scraper writes (section 1c) — missing, the venue gets no map link.
   A venue with more than one space can list several addresses, each with its own
   map link (see "A venue with more than one space" in 1c).
4. **Coordinates** in `docs/data/venue_coordinates.json` for each address: run
   `python geocode_venues.py` after adding the address (it only looks up what is
   missing, section 1c-ii). `tests/test_venue_coordinates.py` fails until every
   address has coordinates, so you will find out if you forget. **Give the address its ZIP or
   postcode**: without one the geocoder can pick a different city's street of the same name (Hauser &
   Wirth DTLA's "901 E 3rd St, Los Angeles" was placed in Long Beach, 25 miles away, until the ZIP was
   added). `--redo "Venue Name"` looks it up again once the address is fixed.

**A Bay Area venue in a town the site hasn't seen** also needs the town added to `AREAS.sf` in
`docs/filterState.js`, under San Francisco, East Bay, Peninsula, South Bay or North Bay: the Area
filter finds a venue's area from the city in its address, and `node --test tests/` fails until
every address in `sf_venues.json` is in one. The same goes for an **Istanbul** venue in a district not
yet in `AREAS.ist` (most districts are already there, including Kadıköy and Üsküdar).

**A Los Angeles venue** needs a **ZIP code in its address** (`"5905 Wilshire Blvd, Los Angeles, CA 90036"`):
most LA venues are in the city of Los Angeles, so the Area filter places them by ZIP (Hollywood and
Mid-Wilshire, Westside, Downtown and South LA, Pasadena and San Gabriel Valley), and a ZIP also stops
the geocoder putting the street in another city. A venue in a nearby town (Santa Monica, Pasadena...) is
placed by the town. `node --test tests/` fails until every address in `la_venues.json` has a ZIP and is
in an area; if it names a ZIP or town not yet listed, add it to the right area in `AREAS.la`.

Then write the real data with `python main.py --venues "<Venue Name>" --no-summary`,
and check it in CI once (section 2a). If the site blocks GitHub's servers, also
see section 2f. Everything below this point is for a whole new city.

---

# Adding a new region (city)

> **Where requests come from.** The "Add my area" button on the home page emails
> `info.artbasil@gmail.com` (through Web3Forms, like the other site forms) with the
> subject "Art Basil: area request - <city or area>", the visitor's notes, and their
> email as the reply-to if they left one. Look there for cities people want before
> choosing the next region.

A "region" is a city / metro area (`sf`, `la`, ...). Each region has its own
event database, venue-address map, scraper package, and front-end page.

Pick a **short lowercase slug** for the region (e.g. `mtl` for Montreal, `tor`
for Toronto). `<region>` below means that slug; `<City>` means the display name.

---

## 1. Backend / scraper pipeline

### 1a. `config.py`
Add the region to `DB_FILES`:
```python
DB_FILES = {
    'sf': 'docs/data/sf_events.json',
    'la': 'docs/data/la_events.json',
    '<region>': 'docs/data/<region>_events.json',
}
```
Everything else keys off `DB_FILES` automatically (`main.py` loads every region
in it, `db_size.csv` lists every region in it).

### 1a-2. `docs/data/regions.json`
Add the region's IANA time zone (e.g. `"<region>": "Europe/Istanbul"`). Event dates
are calendar days at the venue, so this decides what "today" is when phases are
advanced. This one file is the source of truth for both sides: `config.py` loads
it (`REGION_TIMEZONES`) and `docs/dataManager.js` fetches it (`regionToday()`) -
nothing to keep in sync. **Easy to forget** - the nightly phase update raises
without it, and so does `regionToday()` in the browser.

### 1b. `docs/data/<region>_events.json`
Create it containing just `{}` and commit it. `load_db()` will create it on the
fly if missing, but committing it keeps the first CI run clean.

### 1c. `docs/data/<region>_venues.json`  ← **easy to forget**
Create a `{ "Venue Name": "Street, City, PROV" }` map. `tableRenderer.js` turns
each address into a Google Maps "directions" link. A venue with **no entry here
gets no map link**. The key must match the scraper's `venue` string byte-for-byte
(see 2c).
```json
{
    "Montreal Museum of Fine Arts": "1380 Sherbrooke St W, Montreal, QC"
}
```
This file is also the *only* source for `docs/<region>/venues.html` (see 3b-2) -
`venuesRenderer.js` renders whatever's in here. **Adding a venue here is the
entire "add it to the venue list page" step** - there's nothing to update on
the front end, for a new region or an existing one. This applies whether the
venue was added by a new scraper (2c) or by hand for a manual submission (see
`SUBMISSIONS.md`).

#### A venue with more than one space
The map link is built from the venue's value, one link per address. For the usual
single address that is a plain string (above). If one venue has **two or more
spaces that list their shows together**, give it a list of `label` + `address`
instead, and each address gets its own link ("Map: Hart House", "Map: King's
College Circle"); the venues page lists them on separate lines:
```json
{
    "Art Museum at the University of Toronto": [
        {"label": "Hart House", "address": "7 Hart House Circle, Toronto, ON M5S 3H3"},
        {"label": "King's College Circle", "address": "15 King's College Circle, Toronto, ON M5S 3H7"}
    ]
}
```
- Every entry needs a short `label` once there are two or more (a test checks
  this); a list with one entry shows a plain "Map" like a string would.
- The `venue` key stays one string, identical in the scraper and in this file (2c).
  An event belongs to one venue, so every event shows **all** the venue's links,
  including shows held in only one of the spaces. That is the trade-off.
- **Or split it into two venues** (two keys, two scrapers or one scraper writing
  two `venue` strings) when the spaces are really separate places: they have their
  own sites or listings, and no show spans both. That is how Hauser & Wirth
  DTLA / WeHo and Salt Galata / Salt Beyoğlu are done, and it gives each event a
  single exact map link. Choose multiple addresses only when one site lists the
  shows of both spaces and some span them (the Art Museum at the University of
  Toronto does).
- Reading the value is done by `docs/venueAddresses.js` (used by both
  `tableRenderer.js` and `venuesRenderer.js`); nothing else in the front end
  needs to change. `submissions.py` also accepts this shape. Before you list
  several addresses, make sure each really is a place to visit (for example,
  a university's own street address in its footer is not a gallery space).

### 1c-ii. `docs/data/venue_coordinates.json` (map and "Near me")  ← **also easy to forget**
Every address in `<region>_venues.json` also needs a latitude and longitude, so the map
and the distances never have to look addresses up in a visitor's browser:
```json
{
    "mtl": {
        "Montreal Museum of Fine Arts": [{"lat": 45.498512, "lng": -73.579431}]
    }
}
```
The list is in the **same order as the venue's addresses**: one entry for a plain address,
one per space for a venue with several. Don't write it by hand; run the geocoder, which
uses OpenStreetMap's public Nominatim service (one request a second, so about 3 minutes
for all 170 venues, seconds for one new venue):
```bash
python geocode_venues.py                      # every address without coordinates
python geocode_venues.py --region mtl         # one region
python geocode_venues.py --redo "Venue Name"  # look a venue up again, e.g. after correcting its address
python geocode_venues.py --dry-run            # list what it would look up
```
It prints what it could not find and what it matched only roughly (an entry marked
`"approx": true`: the street or the area, not the building). Check those on a map, then fix the
address in the venues file and `--redo`, or edit the coordinates by hand and add
`"manual": true` so the script never touches them again.

A new **region** also needs a bounding box in `docs/data/region_bounds.json`
(`{"lat": [south, north], "lng": [west, east]}`, generous, covering every venue). The geocoder only
accepts a match inside it, and `tests/test_venue_coordinates.py` fails if any coordinate falls
outside, which catches an address matched in the wrong city.
The "Use my location" button (`docs/nearMe.js`) also needs the region's **distance units** in its `UNITS`
map (`'mi'` or `'km'`); a test fails until it has one. Map view opens framed on the same box, so make it cover
every venue without leaving a lot of empty map around them.

### 1d. `scrapers/<region>/`
New directory, one module per venue. **No `__init__.py`** — the project uses
plain directory imports.

### 1e. `main.py`
Import the new modules and add a region block to `all_scrapers` in
`get_venue_scrapers()`:
```python
from scrapers.<region> import venue_one, venue_two

all_scrapers = {
    'sf': { ... },
    'la': { ... },
    '<region>': {
        "Venue One": venue_one.scrape_venue_one,
        "Venue Two": venue_two.scrape_venue_two,
    },
}
```
A region with no `selected_regions` filter runs automatically once it's here.

### 1f. `.github/workflows/scrape-exhibitions.yml`  ← **easy to forget**
Add the new events file to the commit step, or CI will scrape the data every day
and never commit it:
```yaml
    - name: Commit and push updated data
      run: |
        ...
        git add docs/data/<region>_events.json
```

---

## 2. Per-venue scraper

Model new scrapers on `scrapers/la/hammer.py` (HTML) or `scrapers/la/moca.py`
(JSON API). Each module exposes:

```python
def scrape_<venue>(env='prod', region='<region>'):
```

### 2a. Fetching
- Use `fetch_and_parse(url)` from `utils` (returns a `BeautifulSoup` or `None`).
- It accepts an optional `headers=` dict to override/extend the default
  `User-Agent` (some CDNs — Cloudflare, Fastly — 403 the default bot UA).
- **A site that loads fine from your laptop can still 403 GitHub's servers.**
  After adding a scraper, check it in CI (`gh workflow run scrape-exhibitions.yml`,
  then grep the job log for `Error fetching <your site>`). If it's blocked, route
  it through the ZenRows proxy — see 2f.
- **A page that is empty or says "Loading..." without JavaScript** usually fills itself in from a
  JSON address, which is free to read and needs no ZenRows `js_render` (25 credits a request). Open
  the page in a browser, look at the network requests, and read that address with
  `fetch_json(url)` from `utils`. Daniel Faria Gallery is a public GraphQL endpoint
  (`fetch_json(url, query=...)`) and Jeffrey Deitch is `/lazystate/<section>`; see
  `scrapers/tor/daniel_faria_gallery.py` and `scrapers/la/jeffrey_deitch.py`.
- **A site that fails with `CERTIFICATE_VERIFY_FAILED`** (the log says `Error fetching ...`):
  find out which kind before giving up on it. *Hostname mismatch* — try the `www.` address
  (Borusan's bare domain has a certificate for another name; `www.` is fine). *Unable to get
  local issuer certificate* — the server doesn't send its intermediate certificate (browsers
  fetch it themselves). Download it from the `CA Issuers` address in the site's certificate,
  add it to `certs/intermediates.pem` and the host to `EXTRA_CA_HOSTS` in `utils.py`
  (`verify_for`); verification stays on. *Certificate has expired* or *tlsv1 unrecognized
  name* — the site's own fault; don't turn verification off, note it on the ticket and retry
  later (Blum & Poe and Galeri Mana were like this in November 2026).
- Always guard `if soup is None:` — log a warning and `return`, don't raise.
  An uncaught exception in one scraper aborts the whole daily run.

### 2b. `event_details` shape (what `process_event` expects)
```python
event_details = {
    'name': event_title,
    'venue': 'Venue Name',              # see 2c
    'description': description or None,
    'tags': ['exhibition', phase, 'museum'],   # phase is 'current' | 'future' | 'past'
    'phase': phase,
    'dates': {'start': start_date, 'end': end_date},   # datetime.date or None
    'ongoing': False,
    'links': [{'link': event_link, 'description': 'Event Page'}],
    'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
}
if image_url:
    event_details['links'].append({'link': image_url, 'description': 'Image'})

if env == 'prod':
    process_event(event_details, region)
```

### 2b-ii. Descriptions

Fill `description` for **every** event, from the start. The site reads it in two places: the **search box**
looks at it (so searching an artist who is in a group show, but not in its title, finds the show:
WEBSITE-39) and **tagging** reads it to add subject tags (photography, ceramics...). An event with no
description can be found only by its title, venue and tags, and the venues where this was skipped
(Toronto, Montreal) are the ones where search finds the least.

- **Where to get it:** the blurb on the listing page, else the event page's own text: its
  `<meta name="description">` or `og:description`, or the first paragraph or two of the exhibition text.
  Take the show's description, not the venue's boilerplate (a museum's "about us" is on every page).
- **What to write:** plain text, one to three sentences, up to about 500 characters. **Keep the artists'
  names**, especially for a group show where they are not in the title. Strip HTML and entities, collapse
  whitespace, and cut at a sentence boundary rather than mid-word.
- **A fallback exists, but don't lean on it.** `descriptions.py` (OPERATIONS.md, "Event descriptions") fills a
  description for events whose scraper left it blank, from the event's own page (or, for shows listed together on one
  page, from the show's own page found from its card on the listing). A few paid-proxy pages a run are fetched, the
  cheapest first (OPERATIONS.md, "Event descriptions"), and it gets nothing from a listing whose cards don't link to
  the shows' own pages, so for those the scraper should supply it. A new proxied venue whose listing already carries a
  blurb should store it: it costs no extra credits.
- **Don't invent one** if the page has nothing: leave `description` as `None`, and say so in the
  scraper's comments. A blank is better than a wrong blurb.
- **Check it:** after a run, count the events with no description. If most are blank for a venue that has
  text on its pages, the selector is wrong:

```bash
python - <<'EOF'
import json
d = json.load(open('docs/data/<region>_events.json'))
events = [e for v in d.values() for e in v.values() if e.get('venue') == '<Venue Name>']
print(len(events), 'events,', sum(1 for e in events if e.get('description')), 'with a description')
EOF
```

A manual entry (`submissions.py`, `SUBMISSIONS.md`) gets the same: ask for the artists.

### 2b-i. Pictures
A show with no `Image` link gets no thumbnail, so capture one in the scraper. Take the
picture shown with the show on the listing page, not a site-wide header or logo, and
look at the result (a logo or banner in the table is worse than no picture):

- **A listing of several shows** (the usual case for a text-reading Toronto-style
  scraper): build the shows with `Listing` from `scrapers/tor/_common.py`. Call
  `listing.add(name, start, end, tag=...)` for each show as you read it, then
  `found = listing.publish()`. `Listing` finds each show's picture on the page (the one
  in the same card as its title; the title can be split over tags and punctuation does
  not matter), skips logo-like and icon files, leaves off a picture that would go to
  more than one show, and stores the show. `link=` sets a show's own Event Page link.
- **One show per page, or a scraper that builds `event_details` itself:** call
  `images.image_in_card(soup, title, page_url, all_titles, check_size=False)` and append
  the result as the `Image` link, as `scrapers/sf/manna_gallery.py` does. Pass every
  show's title as `all_titles` on a listing so a card with no picture can't borrow its
  neighbour's. It also reads CSS background images and lazy-loaded `data-src` pictures.
- **A show with its own page:** link to that page as the Event Page. If the scraper
  supplies no image, `images.py` opens the page after the scrapers run and picks one (see
  "Event images" in [OPERATIONS.md](OPERATIONS.md)).
- **A page built by JavaScript** may still hold the picture in a JSON blob inside a
  `<script>` tag; look there before giving up (see `scrapers/sf/creative_growth.py`).
- Pictures must load over https from another site (the site is https). An http-only host
  needs `images.secure_image_url(url)`, which routes it through a free https image proxy
  (`image_in_card` already does this); a host that blocks other sites embedding its
  pictures will not show them.
- **No picture to find?** Add the venue's logo to `docs/data/venue_images.json` (venue
  name to image URL, exactly as the scraper's `venue` string). The table shows it for that
  venue's events that have no picture (OPERATIONS.md, "Event images").

Scrapers only set the type, phase and venue-kind tags above. Don't add subject
tags (photography, ceramics, latinx, ...) yourself: `process_event` adds them
from the title and description using the rules in `tagging.py`.

### 2c. The `venue` string
`event_details['venue']` is the identity key everywhere:
- it's the top-level key in `<region>_events.json`
- `tableRenderer.js` looks it up in `<region>_venues.json` for the map link(s)
  (one per address; see "A venue with more than one space" in 1c)

It must be **identical** in the scraper and in `<region>_venues.json`. A mismatch
= events with no map link (and the broken-image / missing-link symptoms that
shows up as on the site).

### 2d. Phase
Derive it from the dates rather than trusting a page's "current/past" tab, using
the helpers in `processing.py` (`today` is in the region's time zone, from
`docs/data/regions.json`):
```python
from processing import process_event, derive_phase, region_today

today = region_today(region)
phase = derive_phase(start_date, end_date, today) or 'current'   # tab's phase as the fallback
```
`processing.update_event_phases()` re-checks past-dated events on every run, so
getting `current` vs `future` slightly wrong self-corrects; `past` should be
right at write time.

### 2e. Parsing dates
`date_parsing.parse_date_text(text, today)` returns `(start, end)` for the
styles venues actually use: `Oct 3–Dec 19, 2026`, `Oct 3rd, 2026–Feb 27, 2027`,
`Oct 3–24, 2026`, `Through January 3` (no year — inferred from `today`) and a
lone `October 10, 2026` (a start date). It returns `(None, None)` when it can't
read the text, so log and skip rather than guess. If a venue uses a style it
doesn't handle, extend it rather than writing a second parser.

### 2f. Venues that block GitHub's servers (the ZenRows proxy)
Some sites (Cloudflare, Vercel and Fastly protections) 403 or challenge GitHub
Actions' IPs while loading fine elsewhere. Those are fetched through the ZenRows
proxy. Adding one takes three steps:

1. **Find the cheapest tier that works — by live test, not by guessing.** In
   `utils.py`, `PROXY_DOMAINS` maps a hostname (exactly as in the URL, so
   `www.` matters) to ZenRows params. `premium_proxy` alone costs 10 credits a
   request; adding `js_render` (needed for JavaScript challenges) costs 25. Several
   sites that looked like plain IP blocks turned out to need `js_render`, and
   ZenRows says so (`RESP001`) when they do.
2. **Register the scraper in `main.py`'s `PROXIED_VENUES`**: scraper name → the
   venue names it writes data under (some scrapers write several). Without this
   it runs daily and spends credits it shouldn't.
3. **Budget it.** The free plan is 5,000 credits a month; one refresh of every
   proxied venue is ~375 credits, so `main.py` refreshes each one only when its
   data is 84+ hours old (every 4 days, ~2,400 credits a month in all, see
   OPERATIONS.md). If the venue has a separate page of past exhibitions, wrap that
   fetch in `past_pages_due(env)` (from `utils`) so it is pulled only about every 8
   days; the scrapers for BAMPFA, Cantor, de Young and Norton Simon show how.
   Out of credits, ZenRows answers `402`; the first one stops all proxying for that
   run and the venues keep their old data. Avoid casual manual CI runs and tier
   experiments: each full run on a due day spends ~375 credits.

Naming a venue in `selected_venues` always runs it, bypassing the gate.

### 2g. Absolute vs relative URLs
When a page gives a relative `src`/`href`, only prepend the base when it's
relative — some sites mix absolute and relative:
```python
url = src if src.startswith('http') else BASE_URL + src
```

---

## 3. Front-end (the `docs/` GitHub Pages site)

### 3a. `docs/dataManager.js`
Add a branch to `getRegion()`:
```js
if (path.includes('/<region>/')) {
    return '<region>';
}
```
(No time zone entry needed here - `regionToday()` reads `docs/data/regions.json`,
added in step 1a-2.)

### 3b. `docs/<region>/index.html`
Copy `docs/sf/index.html` verbatim, then change exactly three things:
- `<title>Art Basil - <City></title>`
- `<h1 class="display-5 mb-3 text-md-end region-title"><City></h1>`
- the region colour on `<body>`: `style="--region-c: <hex>; --region-t: <tilt>deg;"` (pick the colour in 3c-2)
(The lead paragraph and everything else is region-agnostic, including the filter panel - `#filterPanel`, `#filterSummary` and the `filterState.js` / `filterPanel.js` scripts - which offers only the tags that region's data has.)

### 3b-2. `docs/<region>/venues.html`  ← **easy to forget**
Copy `docs/sf/venues.html` verbatim, then change exactly three things:
- `<title>Art Basil - <City> Venues</title>`
- `<h1 class="display-5 mb-3 text-md-end region-title"><City></h1>`
- the same `--region-c` / `--region-t` style on `<body>` as the region's `index.html`
Nothing else is region-specific - `venuesRenderer.js` detects the region from
the URL path the same way `dataManager.js` does (3a) and fetches
`<region>_venues.json` (1c) itself. Also add the link to it from the region's
own `index.html`, in the `header-region` block, below the button row:
```html
<p class="mt-3 mb-0 text-md-end"><a href="venues.html">List of venues</a></p>
```

### 3c. `docs/index.html`
Add a blob inside `<nav class="region-blobs">`, next to the existing ones:
```html
<a href="<region>/index.html" class="region-blob shape-a" aria-label="<Full city name>"
   style="--c: <hex>; --t: 1.8deg; --w: 220px; --dur: 6s">
    <span class="region-name"><City></span>
    <span class="region-meta" data-region="<region>"></span>
</a>
```
- `--c` is the region colour (3c-2). `--t` is the tilt (alternate the sign down the
  row), `--w` the width (the biggest region gets the biggest blob), `--dur` the
  bobbing speed (5.5s to 7.5s, different for each). `shape-a`, `shape-b` or
  `shape-c` picks the blob outline; vary it between neighbours.
- The "N venues" line fills itself in from `<region>_venues.json` (1c), so there is
  nothing else to change.

### 3c-2. Pick the region's colour
One colour per region, used for the home blob, the page title, filters, links and
buttons. Take the next unused one, in this order:

| Used by | Colour | Hex |
|---|---|---|
| San Francisco Bay Area | green | `#14806b` |
| Los Angeles | orange | `#c4520f` |
| Montreal | blue | `#3358d6` |
| Toronto | purple | `#8f3fc0` |
| Istanbul | red | `#c93631` |
| *next 1* | magenta | `#b8227a` |
| *next 2* | cyan | `#00748f` |
| *next 3* | olive | `#5f7a0a` |
| *next 4* | sky | `#1c78c0` |
| *next 5* | sunshine yellow | `#ffc61a` — **not wired up yet**, see below |

These were chosen to read white text at 4.5:1 or better and to sit at least 25
(CIE76 distance) away from every colour already in use. **Check any other colour
the same way** before using it; most hues are already taken, and the closest
existing pair (Los Angeles and Istanbul) is only 23 apart.

**Sunshine yellow needs dark text.** White text on `#ffc61a` is 1.6:1, and yellow
text on a light page is unreadable. Before using it, add two variables (for
example `--region-on`, the text colour on blobs and filled buttons, and
`--region-ink`, the colour for the title and links), default them to white and
`--region-c`, and set them to near-black for that region. Nothing uses them yet.

### 3d. `docs/add_event.html`
Add the new city in three places: a chip in the "We cover" line, in the region's
colour (3c-2), and an `<option>` in each of the two Region menus (the event form
and the venue-suggestion form):
```html
<span class="region-chip" style="--c: <hex>"><City></span>
<option><City></option>
```

---

## 4. Docs / housekeeping

- `README.md` — update the `*Location:*` line.
- `docs/JS_REFACTOR_README.md` — update "Detects current region (SF/LA)".

---

## 5. Verify before committing

```bash
# region wired into the registry
python -c "import main; v,_ = main.get_venue_scrapers(selected_regions=['<region>']); print(list(v))"

# each scraper runs without writing to the DB
python - <<'EOF'
import logging; logging.basicConfig(level=logging.WARNING)
from scrapers.<region> import venue_one
cap = []
venue_one.process_event = lambda ev, r: cap.append(ev)
venue_one.scrape_venue_one(env='prod', region='<region>')
print(len(cap), 'events')
assert all(e['dates'] for e in cap)
EOF
```

Checklist:
- [ ] every scraper fills `description` (2b-ii): no venue with mostly blank descriptions unless its pages
      have none
- [ ] every scraper's `venue` string has a matching key in `<region>_venues.json`
      (a venue with several spaces: a list of `label` + `address`, see 1c)
- [ ] every address has coordinates in `docs/data/venue_coordinates.json` (`python
      geocode_venues.py`, 1c-ii) and the region has a box in `docs/data/region_bounds.json`
      and its distance units (`mi` or `km`) in `UNITS` in `docs/nearMe.js`
- [ ] `<region>_events.json` committed (as `{}`)
- [ ] workflow `git add` line added
- [ ] `docs/<region>/index.html` created, `docs/index.html` card added,
      `getRegion()` branch added
- [ ] `docs/<region>/venues.html` created, linked from `index.html`
- [ ] time zone added to `docs/data/regions.json`
- [ ] dev run of each scraper produces dated events
- [ ] each scraper has run once in CI, with no `Error fetching` for its site in the job log
- [ ] if a venue needed the proxy: in `PROXY_DOMAINS` **and** `PROXIED_VENUES`
