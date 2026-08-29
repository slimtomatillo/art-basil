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
Derive it from the dates rather than trusting a page's "current/past" tab:
```python
if end_date and end_date < today:      phase = 'past'
elif start_date and start_date > today: phase = 'future'
else:                                   phase = 'current'
```
`processing.update_event_phases()` re-checks past-dated events on every run, so
getting `current` vs `future` slightly wrong self-corrects; `past` should be
right at write time.

### 2e. Absolute vs relative URLs
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

### 3b. `docs/<region>/index.html`
Copy `docs/sf/index.html` verbatim, then change exactly two things:
- `<title>Art Basil - <City></title>`
- `<h1 class="display-5 mb-3 text-md-end"><City></h1>`
(The lead paragraph and everything else is region-agnostic.)

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
- [ ] dev run of each scraper produces dated events
