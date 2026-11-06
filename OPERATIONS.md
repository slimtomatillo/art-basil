# Running and maintaining Art Basil

Day-to-day operation: what runs automatically, how to tell when something is
wrong, and what to do about it. To add a scraper, see
[ADDING_A_REGION.md](ADDING_A_REGION.md); for emailed events, see
[SUBMISSIONS.md](SUBMISSIONS.md).

## What runs automatically

`.github/workflows/scrape-exhibitions.yml` is set to start every day at about
4am Pacific (12:17 UTC in winter, PST; 11:17 UTC in summer, PDT). Cron has no
time zones, so **change the hour when the clocks change** (mid March and early
November). GitHub also starts scheduled runs late when it is busy, most of all at
the start of an hour, so the minute is off the hour; before that change the runs
were starting 4 to 9 hours after their time, and a run can still be late. A
manual run is `gh workflow run "Daily Exhibition Scraper" --ref main`.

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
- **Shows not seen on the venue's site** — a current or upcoming event its working
  scraper hasn't reported for 21 days. The stale-venue check can't see these: while a
  scraper refreshes a venue's other events the venue looks healthy, yet a show that
  dropped off the listing, or moved to a page the scraper doesn't read, would otherwise
  sit on the site as current or upcoming forever (LACMA's permanent installations did,
  because its "Ongoing" tab wasn't scraped). For each one, look at the venue's site:
  if the show is over, mark it past by hand or let it age out; if it is still on, the
  scraper is missing a page or a layout, so fix the scraper.
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
Huntington, AGO, Southern Exposure, Asian Art Museum, Art Museum at the University of Toronto,
Armory Center for the Arts, Marin Civic Center) block GitHub's servers, so they are fetched
through the [ZenRows](https://www.zenrows.com) proxy. The list of hostnames and
the ZenRows options each needs is `PROXY_DOMAINS` in `utils.py`; the API key is
the repository secret `SCRAPER_PROXY_API_KEY`. Without the key those scrapers
fall back to a direct fetch, fail, and keep their old data.

**Credits are the constraint.** The free plan gives 5,000 credits a month. A
request costs 10 credits with `premium_proxy` and 25 with `premium_proxy` +
`js_render`. One refresh of every proxied venue is about 375 credits: about 255
for the current and upcoming pages, and about 120 for the past-exhibition pages
(BAMPFA, Cantor, de Young / Legion of Honor, Norton Simon, Asian Art Museum).
Refreshing everything daily would need about 11,400 a month. Instead:

- `main.py` refreshes a proxied venue only when its newest stored event is 84+
  hours old, which is **every 4 days** (about 7.6 refreshes a month). The other
  daily runs skip it. The registry is `PROXIED_VENUES` in `main.py`; a new
  proxied scraper must be added there or it will run daily.
- **Past-exhibition pages are pulled only on every second refresh** (about every
  8 days), because they change rarely. The choice comes from the calendar
  (`utils.past_pages_due`: `date.toordinal() // 4` is even), so there is no stored
  state. A scraper with a past page wraps that fetch in `past_pages_due(env)`.
- That comes to about **2,400 credits a month** (255 x 7.6 + 120 x 3.8), around
  half the allowance, which leaves about 2,600 for new proxied venues. A venue
  with one 10-credit page costs about 76 a month, and one 25-credit page about 190.
- **Marin Civic Center needs `js_render`** (25 credits a request, about 190 a month): with
  `premium_proxy` alone ZenRows answered 422 in CI. A refused proxy request now logs ZenRows's
  explanation (the response body), so a 422 or similar says why in the run log.
- A failed fetch leaves a venue's data old, so it is retried on the next daily
  run rather than waiting another 4 days. (The stale-data check flags a venue
  after 7 days.)
- On the first `402` in a run, all proxying stops for that run and the remaining
  proxied venues are skipped with one warning.
- `--venues` always runs the venue, ignoring the 4-day gate, and fetches its past
  pages too.

So avoid manual workflow runs on a day when the proxied venues are due, and
avoid live-testing ZenRows options casually: each spends real credits. Check
remaining credits in the ZenRows dashboard; the figures above are estimates from
counting each scraper's fetches, not measured usage. The schedule is covered by
`tests/test_proxy_schedule.py`. If 4-day freshness isn't enough, the alternative
is a paid ZenRows plan.

To add a blocked site, see section 2f of [ADDING_A_REGION.md](ADDING_A_REGION.md).

## Forms and feedback (Web3Forms)

The Add Event page (an event form and a "suggest a venue" form) and the "?" feedback
dialog send their messages to info.artbasil@gmail.com through
[Web3Forms](https://web3forms.com), so the site stays static with no backend. The
shared sender is `docs/web3forms.js`; `docs/siteForms.js` drives the Add Event forms
and `docs/feedback.js` the dialog.

- **The access key** is the `WEB3FORMS_ACCESS_KEY` constant at the top of
  `docs/web3forms.js`. It is meant to be public (it can only send mail to the inbox
  it was created for), so it is committed. While it is empty every form fails with
  an honest "did not send, email us instead" message and a prefilled `mailto:` link;
  nothing is ever reported as sent unless Web3Forms accepted it.
- **Limits:** the free plan allows 250 submissions a month and has no domain
  allowlist, so anyone who copies the key can send to the inbox until the cap. Spam
  protection is a hidden checkbox (`botcheck`) plus rejecting a submit sooner than
  2.5 seconds after the form appeared; both pretend to succeed and send nothing. If
  junk gets through, add Web3Forms' hCaptcha (free) or move to a paid plan with
  trusted domains. Check the cap and history in the Web3Forms dashboard.
- **Emails** list every filled-in field under its label (Region, Event title, Venue,
  ...); the submitter's address, if given, is the reply-to.
- **Testing:** the forms' logic is covered by `node --test tests/` with a faked
  network. To test for real, submit each form once and check the inbox.

## Subject tags

Subject tags (medium and theme) are added automatically by the keyword rules in
`tagging.py`, to every event, whenever it is saved. Adding a tag is a deliberate
step: draft its rule in `PROPOSED`, get the tag approved, then add it to
`APPROVED_TAGS` and to `docs/tags.html`. After editing any rule, apply it to the
events already stored with:

```bash
python tagging.py        # safe to repeat; only ever adds tags, never removes or changes anything else
```

Rules match the title and description with the venue's own name blanked out, and
the identity-based tags (`asian-american`, `latinx`, `black-art`, `indigenous`,
`queer`) fire only on explicit language in the venue's text,
never on place names or an artist's origin. A missing tag is invisible and a
wrong one is a visible error, so prefer a rule that is slightly too narrow. A
tag a person added by hand is never removed.

### The `free` tag (admission)

`free` follows from the venue, not the text. Two rules in `tagging.py` (`venue_tags`):
every gallery that isn't a museum is free, and every venue recorded as `free` in
`docs/data/venue_admission.json` is free. That file has one entry per museum and
art center, by region and venue name: `admission` (`free`, `paid` or `unverified`),
the `source` page, the date `checked`, and a `note` (free days, parking, and so on).
Only `free` is tagged. `free` means free to see the exhibitions: a suggested
donation counts, but pay-what-you-wish, free-for-residents-only or free-some-days
venues are `paid` (the free days go in the note). A show without `free` means "not
known to be free", not "paid".

- **A new museum or art center:** add its entry (a test fails until you do), read the
  price off the venue's own site, then run `python tagging.py` to tag its events.
- **Re-checking:** policies change (MOCA, Hammer and MOCA Toronto have all changed
  theirs in recent years). About once a year, or when a venue announces a change, open
  each venue's `source`, update the entry and its `checked` date, and re-run
  `python tagging.py`. Note it only ever adds tags: if a venue stops being free, remove
  `free` from its events by hand (or with a one-off script), since `tagging.py` never
  removes tags.
- **First pass, 2026-11-06:** prices were looked up by web search, and some entries rest
  on third-party listings rather than the venue's own page (the notes say so for the
  Asian Art Museum and the Walt Disney Family Museum). `unverified` entries
  (Marin MOCA, Elgiz, Madrone Art Bar) need a direct check.

## Event images

Pictures come from two places, and a wrong picture is worse than none:

1. **The scraper**, which is the main source. A scraper takes each show's picture from
   the card that holds its title on the listing page (`Listing` in
   `scrapers/tor/_common.py`, or `images.image_in_card`; see ADDING_A_REGION.md 2b-i).
   This covers most Toronto venues and Manna, Shooting Gallery and the Art Museum at
   U of T.
2. **A fallback, `images.py`**, which runs after the scrapers. It opens the page of each
   current or upcoming event that still has no image and picks a picture from it (the
   page's share image first, then its own pictures). Events that share one listing page
   are looked up together by title, the same way as in a scraper.

Either way a picture is skipped if it is an SVG, is named like a logo, icon, badge or
placeholder (or sits in an `icons/` or `logos/` folder), or is used for more than one
of a venue's shows (then it is a banner). The fallback also needs a picture of at least
25 KB; scrapers don't, since small thumbnails are fine.

- The result is stored as a normal `Image` link, so the table shows it like any other.
  `processing.py` keeps it when the scraper rewrites the event later; a scraper that
  supplies its own image always wins.
- `image_checked` on an event is the day it was last looked at; events with nothing
  found are retried every 14 days, not daily. At most 80 pages are opened per run, so a
  backlog clears over a few days.
- Pages on proxied sites are skipped (an extra fetch would spend ZenRows credits), and
  hand-entered and archived events are left alone.
- **Tracking what's still missing:** every daily run rewrites [IMAGE_AUDIT.md](IMAGE_AUDIT.md)
  (`image_audit.py`) and adds its summary to the Actions job summary. For current and
  upcoming events it gives the share with their own picture, the venues whose events show
  only the venue logo or nothing, and each such event with its page and the day its page
  was last checked. The file is committed with the data, so its history shows coverage
  over time. Print it on demand with `python image_audit.py`. Nothing is fetched for the
  audit; looking again for a better picture happens by itself (scrapers on every run,
  `images.py` every 14 days for an event with no picture), so the audit is the list for a
  person: a venue sitting in it run after run needs a better scraper, or a logo in
  `venue_images.json`. On the 1st of each month the "Monthly Picture Audit Reminder"
  workflow (`.github/workflows/image-audit-reminder.yml`) opens a GitHub issue, labelled
  `image-audit`, holding the latest audit, and closes last month's. It can also be run by
  hand from the Actions tab.
- Try it without changing any data: `python images.py [region ...]` prints what it would
  add and which pictures it rejected as shared.
- **A venue's logo stands in when an event has no picture.** `docs/data/venue_images.json`
  maps a venue name to a logo or banner URL; the table shows it (kept whole, on a white
  tile) for any of that venue's events with no `Image` link, and a real picture replaces
  it as soon as one is found. To add one, find the logo on the venue's site (its
  `og:image`, a header image or `apple-touch-icon`), check it loads from another site,
  and add a line. The name must match the venue's `venue` string exactly. A venue with no
  logo online (or a site that isn't up yet) can have one kept in the repo: put the file in
  `docs/images/venues/` and give its site path, e.g. `"/images/venues/kubart-gallery.jpg"`. Today it covers
  Marin Society of Artists (its pages carry only the society's logo), Sanchez Art Center,
  Creative Growth, Jessica Silverman and Paul Petro. After a daily run, a venue that
  still shows blank thumbnails is a candidate: look for it with
  `python images.py` (events listed as not found) or on the site.
- **http-only sites** (Sanchez Art Center) can't show their pictures on our https pages,
  so those pictures go through `images.weserv.nl`, a free image proxy
  (`images.secure_image_url`). If that service ever goes away, those thumbnails vanish
  quietly (the page hides a broken picture) and the logo fallback does not apply to them;
  copying the files into `docs/` would be the replacement.
- **Heavy pictures are shrunk automatically.** Some venues serve full-size originals (CAAM's
  are 5-8 MB PNGs). After each scrape `images.shrink_heavy_images` measures every current and
  upcoming event's picture from its response headers (nothing is downloaded) and swaps any over
  700 KB for a small JPEG copy from the same proxy (`images.resized_image_url`), but only after
  checking that the proxy really serves it, so a site that blocks the proxy keeps its original.
  Scrapers write the original link again on their next run and the step repeats, so it is
  redone daily. The table also lazy-loads thumbnails, so rows below the fold load their pictures
  as they are scrolled to. The copy is a JPEG, so a transparent logo would lose its transparency:
  that is why only event pictures are shrunk, never `venue_images.json`.
- `image_checked` only counts while an event still points at the same Event Page. When a
  scraper starts linking a show's own page instead of a listing, the page is looked at
  again on the next run rather than after 14 days.
- Creative Growth's picture is not in its page's HTML: the page is built by JavaScript
  from a JSON blob, which its scraper reads (the image block that links to the show's
  page), and the Event Page link now goes to the show's own page.
- Paul Petro's listing has no pictures, so its scraper links each show to the show's own
  page and the fallback takes the picture from there.

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
