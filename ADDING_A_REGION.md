# Adding a new region (city)

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

### 2c. The `venue` string
`event_details['venue']` is the identity key everywhere:
- it's the top-level key in `<region>_events.json`
- `tableRenderer.js` looks it up in `<region>_venues.json` for the map link

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
3. **Budget it.** The free plan is 5,000 credits a month; a full refresh of every
   proxied venue is ~315 credits, so `main.py` refreshes each one only when its
   data is 60+ hours old (about every 3 days). Out of credits, ZenRows answers
   `402`; the first one stops all proxying for that run and the venues keep their
   old data. Avoid casual manual CI runs and tier experiments — each full run on a
   due day spends ~315 credits.

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
Copy `docs/sf/index.html` verbatim, then change exactly two things:
- `<title>Art Basil - <City></title>`
- `<h1 class="display-5 mb-3 text-md-end"><City></h1>`
(The lead paragraph and everything else is region-agnostic.)

### 3b-2. `docs/<region>/venues.html`  ← **easy to forget**
Copy `docs/sf/venues.html` verbatim, then change exactly two things:
- `<title>Art Basil - <City> Venues</title>`
- `<h1 class="display-5 mb-3 text-md-end"><City></h1>`
Nothing else is region-specific - `venuesRenderer.js` detects the region from
the URL path the same way `dataManager.js` does (3a) and fetches
`<region>_venues.json` (1c) itself. Also add the link to it from the region's
own `index.html`, in the `header-region` block, below the button row:
```html
<p class="mt-3 mb-0 text-md-end"><a href="venues.html">List of venues</a></p>
```

### 3c. `docs/index.html`
Add a city card next to the existing two:
```html
<div class="col-md-6 col-lg-4">
    <a href="<region>/index.html" class="text-decoration-none">
        <div class="card h-100 shadow-sm hover-card">
            <div class="card-body text-center">
                <h2 class="h4 mb-3"><City></h2>
                <p class="text-muted">Discover <City>'s art scene</p>
            </div>
        </div>
    </a>
</div>
```

### 3d. `docs/add_event.html`
Update the region hint line (currently `Region (SF Bay Area or LA)`) to include
the new city.

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
- [ ] every scraper's `venue` string has a matching key in `<region>_venues.json`
- [ ] `<region>_events.json` committed (as `{}`)
- [ ] workflow `git add` line added
- [ ] `docs/<region>/index.html` created, `docs/index.html` card added,
      `getRegion()` branch added
- [ ] `docs/<region>/venues.html` created, linked from `index.html`
- [ ] time zone added to `docs/data/regions.json`
- [ ] dev run of each scraper produces dated events
- [ ] each scraper has run once in CI, with no `Error fetching` for its site in the job log
- [ ] if a venue needed the proxy: in `PROXY_DOMAINS` **and** `PROXIED_VENUES`
