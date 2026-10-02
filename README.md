# Art Basil
You may have heard of Art Basel ([wikipedia](https://en.wikipedia.org/wiki/Art_Basel), [art basel site](https://www.artbasel.com/?lang=en))...but have you heard of Art Basil?

**Purpose**  
This project aims to create and populate (with fresh data!) a website that lists upcoming art events in your area.

**Scope**  
- *Location:* **San Francisco Bay Area**, **Los Angeles**, **Montreal**, **Toronto**, and **Istanbul** for now, more regions coming soon!
- *Events:* Art shows + art-related events (e.g. workshops, talks, tours) at museums, galleries, and colleges/universities.

**Where the data comes from**  
Events live in `docs/data/<region>_events.json`. Each one comes from one of three places, marked by its `source` field:
- *Scraped* (no `source` field): a scraper in `scrapers/<region>/` refreshes it every day. If a venue's data stops refreshing for a week, the daily run flags it as stale. See [ADDING_A_REGION.md](ADDING_A_REGION.md).
- *Manual* (`"source": "manual"`): added by hand from an emailed submission. `manual_check.py` re-checks these daily. See [SUBMISSIONS.md](SUBMISSIONS.md).
- *Archive* (`"source": "archive"`): a one-time import of a closed venue's exhibition history. Nothing refreshes or re-checks it, by design, and the stale check skips it.

**Closed venues**  
- *Cartoon Art Museum* (SF): closed its galleries in 2026. Its history (1988–2026) was imported once as archive data for [WEBSITE-33](https://artbasil.atlassian.net/browse/WEBSITE-33). It has no scraper and, on purpose, no entry in `sf_venues.json`, so it stays off the venues page. If it reopens, build a regular scraper.

**Acknowledgements**  
- This project was inspired by [19hz.info](https://19hz.info/eventlisting_BayArea.php) which has local listings for electronic music events.
- Thank you to [Chris Nager](https://github.com/chrisnager/) for the [squirtle cursor](https://github.com/chrisnager/cursors/blob/gh-pages/squirtle.cur)! You can see some of Chris's other curors in his [repo](https://github.com/chrisnager/cursors).

© A. Smith
