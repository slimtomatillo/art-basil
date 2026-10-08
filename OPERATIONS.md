# Running and maintaining Art Basil

Day-to-day operation: what runs automatically, how to tell when something is
wrong, and what to do about it. To add a scraper, see
[ADDING_A_REGION.md](ADDING_A_REGION.md); for emailed events, see
[SUBMISSIONS.md](SUBMISSIONS.md).

## What runs automatically

`.github/workflows/scrape-exhibitions.yml` runs every day at 4am Pacific
(11:00 UTC):

1. runs `python main.py` (all regions; takes about 10 minutes)
2. commits the changed `docs/data/*_events.json` files and `db_size.csv` as
   "Update exhibition data [skip ci]" and pushes to `main`, which publishes the
   site (GitHub Pages)

The run goes **red** (and GitHub emails you) if any scraper crashed. The other
scrapers still run and their data is still committed. You can also start a run
by hand with `gh workflow run scrape-exhibitions.yml --ref main`, but see
[the proxy section](#proxied-venues-and-the-zenrows-budget) first.

## Knowing something is wrong

At the end of each run, the **job summary** on the Actions run page lists:

- **Crashed scrapers** — a scraper raised an exception (`scraper_health.py`)
- **Stale venues** — a venue whose newest scraped event hasn't been refreshed
  in 7 days. A blocked or redesigned site usually just logs an error and
  carries on, so this is how silent failures get caught. Manual and archive
  events are ignored.
- **Manual events to review** — hand-entered events whose show is about to end,
  or whose page disappeared (`manual_check.py`)

For detail, read the job log. The most useful search is for the venue name, or
`WARNING` / `ERROR`:

```bash
gh run list --workflow=scrape-exhibitions.yml --limit 3
JOB=$(gh run view <run-id> --json jobs -q '.jobs[0].databaseId')
gh api /repos/slimtomatillo/art-basil/actions/jobs/$JOB/logs | grep -E " - (WARNING|ERROR) - "
```

## A venue stopped updating

Find the venue in the log, then work out which of these it is:

| What the log shows | Cause | Fix |
|---|---|---|
| `Error fetching <url>: 403` / `429`, or a "Just a moment" page, but the site loads fine in your browser | The site blocks GitHub's servers | Route it through the proxy (below) |
| `402 Payment Required` from `api.zenrows.com` | The ZenRows credits are used up | Wait for the monthly reset, or buy a plan (below) |
| `Read timed out` from `api.zenrows.com` | A slow proxy render | Retried once automatically; if it persists, check the site manually |
| An `AttributeError` / `NoneType` crash or warning inside the scraper, or "found 0 events" | The site's page layout changed | Fix the scraper's selectors; look at the live page first |
| Nothing wrong in the log, but no events | The venue may genuinely have none (a closed museum, a gap between seasons) | Check the venue's site |

Reproduce a problem locally without writing any data:

```bash
python main.py --env dev --venues "Wattis Institute" --no-summary
```

Several expected warnings appear in every run and are not problems (as of
October 2026): the Contemporary Jewish Museum is temporarily closed so it has no
current or upcoming shows, and a few old archive entries (SF Women Artists,
ICA San Jose) have no dates anywhere on their pages.

## Running scrapers by hand

`main.py` takes options (run `python main.py --help`):

```bash
python main.py                                  # everything, as CI does
python main.py --regions sf la                  # whole regions
python main.py --venues "AGO" "Wattis Institute"   # named venues (quote names)
python main.py --skip-venues "SFMOMA"           # everything except these
python main.py --env dev                        # log only; writes nothing
python main.py --no-summary                     # skip the phase update, health checks, db_size.csv
```

Unknown region or venue names are rejected with the list of valid ones.
Without `--env dev` this writes to `docs/data/*_events.json`; CI commits to
`main` every day, so `git pull --rebase` before you push.

To look at the site locally, serve the `docs/` folder and open a region page:

```bash
python3 -m http.server -d docs      # then http://localhost:8000/sf/
```

## Proxied venues and the ZenRows budget

A few sites (BAMPFA, Cantor, de Young / Legion of Honor, Norton Simon,
Huntington, AGO, Southern Exposure) block GitHub's servers, so they are fetched
through the [ZenRows](https://www.zenrows.com) proxy. The list of hostnames and
the ZenRows options each needs is `PROXY_DOMAINS` in `utils.py`; the API key is
the repository secret `SCRAPER_PROXY_API_KEY`. Without the key those scrapers
fall back to a direct fetch, fail, and keep their old data.

**Credits are the constraint.** The free plan gives 5,000 credits a month. A
request costs 10 credits with `premium_proxy` and 25 with `premium_proxy` +
`js_render`. A full refresh of every proxied venue is about 315 credits, so
refreshing them daily would need about 9,500 a month. Instead:

- `main.py` refreshes a proxied venue only when its newest stored event is 60+
  hours old, which is about every 3 days (~3,200 credits a month). The other
  daily runs skip it. The registry is `PROXIED_VENUES` in `main.py`; a new
  proxied scraper must be added there or it will run daily.
- A failed fetch leaves a venue's data old, so it is retried on the next daily
  run rather than waiting another 3 days.
- On the first `402` in a run, all proxying stops for that run and the remaining
  proxied venues are skipped with one warning.
- `--venues` always runs the venue, ignoring the 3-day gate.

So avoid manual workflow runs on a day when the proxied venues are due, and
avoid live-testing ZenRows options casually: each spends real credits. Check
remaining credits in the ZenRows dashboard. If 3-day freshness isn't enough, the
alternative is a paid ZenRows plan.

To add a blocked site, see section 2f of [ADDING_A_REGION.md](ADDING_A_REGION.md).

## Fixing data by hand

- **A missing event:** add it with `submissions.py` (see
  [SUBMISSIONS.md](SUBMISSIONS.md)); hand-entered events are tagged
  `"source": "manual"`.
- **A wrong or unwanted event:** edit or delete its entry in
  `docs/data/<region>_events.json` (an event's key is `title-venue`; keep it
  matching its `name` and `venue`). A scraped event comes back on the next
  scrape if the scraper still finds it, so fix the scraper if the cause is
  there.
- **A closed venue's history:** imported once with `"source": "archive"`. No
  scraper refreshes it, and the stale check skips it.
- **A renamed venue:** the venue name is the key in `<region>_events.json` and in
  each event's id (`title-venue`), and must match `<region>_venues.json`. Change
  all of those together, or the scraper will treat everything as new.
- **Phases** (current / future / past) are recomputed from the dates at the end
  of every run, and again in the browser on each visit, in the venue's local time
  zone (`docs/data/regions.json`). They only move forward.
