"""Surface scraper problems that would otherwise pass silently.

Two things end up here: scrapers that crashed during this run (main.py catches
them so one broken scraper can't take down the rest), and venues whose scraped
data has stopped refreshing - a blocked or redesigned site usually just logs an
error and carries on, which is how de Young and Cantor went ~5-10 months
unnoticed. Results go to the log and the GitHub Actions job summary.
"""

import datetime as dt
import logging
import os

from config import DB_FILES
from manual_check import MANUAL_SOURCE
from utils import load_db

STALE_AFTER_DAYS = 7
# A current or upcoming event the scraper hasn't seen for this long, at a venue that is otherwise refreshing
UNSEEN_AFTER_DAYS = 21
# One-time imports of a closed venue's history (e.g. the Cartoon Art Museum,
# WEBSITE-33). No scraper refreshes them, by design.
ARCHIVE_SOURCE = 'archive'


def find_stale_venues(today=None):
    """Venues whose scraped events haven't been refreshed in STALE_AFTER_DAYS.

    Every successful scrape rewrites last_updated, so a venue whose freshest
    event is old is one no scraper is reaching. Manually-entered and archive
    events are ignored - nothing refreshes those by design.
    """
    today = today or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    stale = []
    for region, path in DB_FILES.items():
        for venue, events in load_db(path).items():
            stamps = [dt.datetime.strptime(e['last_updated'], '%Y-%m-%d %H:%M:%S')
                      for e in events.values()
                      if e.get('source') not in (MANUAL_SOURCE, ARCHIVE_SOURCE) and e.get('last_updated')]
            if not stamps:
                continue
            days = (today - max(stamps)).days
            if days > STALE_AFTER_DAYS:
                stale.append({'region': region, 'venue': venue, 'days': days})
    return sorted(stale, key=lambda s: -s['days'])


def find_unseen_events(today=None, stale=None):
    """Current or upcoming events a working scraper no longer sees.

    A venue-level check can't catch these: while the scraper refreshes the venue's other events the
    venue looks healthy, yet a show that dropped off the listing (or lives on a page the scraper
    doesn't read, as LACMA's "Ongoing" tab was) is never refreshed again and stays on the site as
    current or upcoming indefinitely. Venues already reported as stale are skipped.
    """
    today = today or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    skip = {(s['region'], s['venue']) for s in (find_stale_venues(today) if stale is None else stale)}
    unseen = []
    for region, path in DB_FILES.items():
        for venue, events in load_db(path).items():
            if (region, venue) in skip:
                continue
            for event in events.values():
                if event.get('source') in (MANUAL_SOURCE, ARCHIVE_SOURCE) or event.get('phase') not in ('current', 'future'):
                    continue
                if not event.get('last_updated'):
                    continue
                days = (today - dt.datetime.strptime(event['last_updated'], '%Y-%m-%d %H:%M:%S')).days
                if days > UNSEEN_AFTER_DAYS:
                    unseen.append({'region': region, 'venue': venue, 'name': event.get('name'), 'days': days,
                                   'phase': event['phase']})
    return sorted(unseen, key=lambda u: (-u['days'], u['venue']))


def find_description_gaps(min_events=3):
    """How many current and upcoming events have a description (WEBSITE-115), and which venues have none.

    Returns ({region: {'live': n, 'described': n}}, [{'region', 'venue', 'live'}]): the venues listed have at
    least `min_events` live events and not one with a description (a scraper that never fills it, or whose
    selector broke). Manually-entered and archive events are left out, as in the other checks."""
    coverage, venues = {}, []
    for region, path in DB_FILES.items():
        live = described = 0
        for venue, events in load_db(path).items():
            counted = [e for e in events.values()
                       if e.get('source') not in (MANUAL_SOURCE, ARCHIVE_SOURCE) and e.get('phase') in ('current', 'future')]
            have = sum(1 for e in counted if e.get('description'))
            live, described = live + len(counted), described + have
            if len(counted) >= min_events and have == 0:
                venues.append({'region': region, 'venue': venue, 'live': len(counted)})
        coverage[region] = {'live': live, 'described': described}
    return coverage, sorted(venues, key=lambda v: (-v['live'], v['region'], v['venue']))


def _percent(part, whole):
    return round(100 * part / whole) if whole else 100


def report(failed, stale, unseen=(), coverage=None, undescribed=()):
    """failed: [(region, venue, error_text)] for scrapers that crashed this run.
    coverage, undescribed: from find_description_gaps()."""
    for region, venue, error in failed:
        logging.error(f"Scraper crashed - [{region}] {venue}: {error}")
    for s in stale:
        logging.warning(f"Scraped data not refreshing - [{s['region']}] {s['venue']}: "
                        f"no update in {s['days']} days")
    for u in unseen:
        logging.warning(f"Not seen on the venue's site - [{u['region']}] {u['venue']}: {u['name']!r} "
                        f"({u['phase']}) last seen {u['days']} days ago")
    for region, c in (coverage or {}).items():
        logging.info(f"Event descriptions - [{region}] {c['described']} of {c['live']} current and upcoming events "
                     f"({_percent(c['described'], c['live'])}%)")
    for v in undescribed:
        # info, not a warning: about thirty venues are listed until WEBSITE-115 is done, and the job summary has the table
        logging.info(f"No event descriptions - [{v['region']}] {v['venue']}: none of its {v['live']} current and upcoming events has one")
    logging.info(f"Finished scraper health check: {len(failed)} crashed, {len(stale)} stale venues, "
                 f"{len(unseen)} events no longer seen")

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write(render_markdown(failed, stale, unseen, coverage, undescribed))


def render_descriptions(coverage, undescribed):
    """The "Event descriptions" section: coverage by region, then the venues with none."""
    lines = ["### Event descriptions", "",
             "Current and upcoming events with a description (the search reads it; see ADDING_A_REGION.md, 2b-ii).", "",
             "| Region | With a description | Share |", "| --- | --- | --- |"]
    live = described = 0
    for region, c in coverage.items():
        live, described = live + c['live'], described + c['described']
        lines.append(f"| `{region}` | {c['described']} of {c['live']} | {_percent(c['described'], c['live'])}% |")
    lines += [f"| **all** | **{described} of {live}** | **{_percent(described, live)}%** |", ""]
    if undescribed:
        lines += [f"Venues with current or upcoming events and **no** descriptions ({len(undescribed)}):", ""]
        lines += [f"- `{v['region']}` **{v['venue']}**: {v['live']} events" for v in undescribed]
        lines.append("")
    return lines


def render_markdown(failed, stale, unseen=(), coverage=None, undescribed=()):
    lines = ["## Scraper health", ""]
    extra = render_descriptions(coverage, undescribed) if coverage else []
    if not failed and not stale and not unseen:
        return "\n".join(lines + ["All scrapers ran and every venue is refreshing.", ""] + extra)
    if failed:
        lines += [f"### Crashed this run ({len(failed)})", ""]
        lines += [f"- `{region}` **{venue}**: {error}" for region, venue, error in failed]
        lines.append("")
    if stale:
        lines += [f"### Data not refreshing for over {STALE_AFTER_DAYS} days ({len(stale)})", "",
                  "Usually a blocked or redesigned site - the scraper logs an error and carries on.", ""]
        lines += [f"- `{s['region']}` **{s['venue']}**: last updated {s['days']} days ago" for s in stale]
        lines.append("")
    if unseen:
        lines += [f"### Shown as current or upcoming but not seen on the venue's site for over {UNSEEN_AFTER_DAYS} days "
                  f"({len(unseen)})", "",
                  "The venue's scraper is working but no longer reports these: the show may have ended or moved "
                  "pages, or the scraper may not read the page it is now on.", ""]
        lines += [f"- `{u['region']}` **{u['venue']}**: {u['name']} ({u['phase']}, last seen {u['days']} days ago)"
                  for u in unseen]
        lines.append("")
    return "\n".join(lines + extra)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    stale = find_stale_venues()
    report([], stale, find_unseen_events(stale=stale), *find_description_gaps())
