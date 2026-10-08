# Art Basil
You may have heard of Art Basel ([wikipedia](https://en.wikipedia.org/wiki/Art_Basel), [art basel site](https://www.artbasel.com/?lang=en))...but have you heard of Art Basil?

**Purpose**  
This project aims to create and populate (with fresh data!) a website that lists upcoming art events in your area.

**Scope**  
- *Location:* **San Francisco Bay Area**, **Los Angeles**, **Montreal**, **Toronto**, and **Istanbul** for now, more regions coming soon!
- *Events:* Art shows + art-related events (e.g. workshops, talks, tours) at museums, galleries, and colleges/universities.

**Where the data comes from**  
Events live in `docs/data/<region>_events.json`. Each one comes from one of three places, marked by its `source` field:
- *Scraped* (no `source` field): a scraper in `scrapers/<region>/` refreshes it every day. If a venue's data stops refreshing for a week, the daily run flags it as stale. A few venues sit behind bot protection that blocks GitHub's servers, so they are fetched through a paid proxy (ZenRows) and refreshed about every 3 days instead, to stay within its free monthly allowance. See [ADDING_A_REGION.md](ADDING_A_REGION.md).
- *Manual* (`"source": "manual"`): added by hand from an emailed submission. `manual_check.py` re-checks these daily. See [SUBMISSIONS.md](SUBMISSIONS.md).
- *Archive* (`"source": "archive"`): a one-time import of a closed venue's exhibition history. Nothing refreshes or re-checks it, by design, and the stale check skips it.

**How it works**  
There is no server. Python scrapers (`scrapers/<region>/`, one module per venue, registered in `main.py`) read each venue's website and write events into `docs/data/<region>_events.json`. A GitHub Actions workflow runs `main.py` every day at 4am Pacific and commits the changed data. The site in `docs/` is plain HTML and JavaScript on GitHub Pages: each page fetches the JSON files directly in the browser.

**Quick start**  
Python 3.12 (what CI uses):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python main.py --env dev --venues "Wattis Institute"   # try one scraper; writes nothing
python main.py --regions sf                            # scrape a region and update its data file
python main.py                                         # everything, as CI does
python3 -m http.server -d docs                         # view the site at http://localhost:8000/sf/
```
`python main.py --help` lists every option. The only secret is the optional `SCRAPER_PROXY_API_KEY` (a [ZenRows](https://www.zenrows.com) key, used for venues that block GitHub's servers); without it those venues just keep their old data.

**Data format**  
`<region>_events.json` maps venue name to events, and each event's key is `title-venue`:
```json
{
  "Wattis Institute": {
    "Alexandre Estrela: RedSkyFalls-Wattis Institute": {
      "name": "Alexandre Estrela: RedSkyFalls",
      "venue": "Wattis Institute",
      "description": null,
      "tags": ["exhibition", "current", "gallery"],
      "phase": "current",
      "dates": {"start": "2026-05-09", "end": "2026-11-21"},
      "ongoing": false,
      "links": [{"link": "https://...", "description": "Event Page"},
                {"link": "https://...", "description": "Image"}],
      "last_updated": "2026-10-08 19:33:17",
      "hash": "5b1fe59b..."
    }
  }
}
```
- `phase` is `current`, `future` or `past`, worked out from `dates` in the venue's local time zone (`docs/data/regions.json`) and only ever moving forward. The dates may be `null`.
- `ongoing: true` means a current show with no end date.
- `tags` start with the type, phase and venue kind the scraper sets (`exhibition`, `current`, `museum`/`gallery`). Subject tags (medium such as `photography` or `ceramics`, and themes such as `latinx` or `woman-artist`) are added automatically from the title and description by `tagging.py` for every event; the approved list is on `docs/tags.html`.
- `source` is absent for scraped events, or `"manual"` / `"archive"` (see above).
- The `venue` string must match a key in `<region>_venues.json`, which maps each venue to its street address (for the map links and the venues page).

**Documentation**  
- [OPERATIONS.md](OPERATIONS.md): the daily run, spotting and fixing a venue that stopped updating, running scrapers by hand, and the proxy and its credit budget.
- [ADDING_A_REGION.md](ADDING_A_REGION.md): adding a venue or a whole region.
- [SUBMISSIONS.md](SUBMISSIONS.md): handling emailed events.
- [docs/JS_REFACTOR_README.md](docs/JS_REFACTOR_README.md): how the front-end modules fit together.
- `notebooks/`: older tools for editing a single combined database file that no longer exists. They are superseded by `submissions.py` and the automatic phase updates, and kept only for reference.

**Closed venues**  
- *Cartoon Art Museum* (SF): closed its galleries in 2026. Its history (1988–2026) was imported once as archive data for [WEBSITE-33](https://artbasil.atlassian.net/browse/WEBSITE-33). It has no scraper and, on purpose, no entry in `sf_venues.json`, so it stays off the venues page. If it reopens, build a regular scraper.

**Acknowledgements**  
- This project was inspired by [19hz.info](https://19hz.info/eventlisting_BayArea.php) which has local listings for electronic music events.
- Thank you to [Chris Nager](https://github.com/chrisnager/) for the [squirtle cursor](https://github.com/chrisnager/cursors/blob/gh-pages/squirtle.cur)! You can see some of Chris's other curors in his [repo](https://github.com/chrisnager/cursors).

© A. Smith
