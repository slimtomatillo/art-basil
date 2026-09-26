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


def find_stale_venues(today=None):
    """Venues whose scraped events haven't been refreshed in STALE_AFTER_DAYS.

    Every successful scrape rewrites last_updated, so a venue whose freshest
    event is old is one no scraper is reaching. Manually-entered events are
    ignored - nothing refreshes those by design.
    """
    today = today or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    stale = []
    for region, path in DB_FILES.items():
        for venue, events in load_db(path).items():
            stamps = [dt.datetime.strptime(e['last_updated'], '%Y-%m-%d %H:%M:%S')
                      for e in events.values()
                      if e.get('source') != MANUAL_SOURCE and e.get('last_updated')]
            if not stamps:
                continue
            days = (today - max(stamps)).days
            if days > STALE_AFTER_DAYS:
                stale.append({'region': region, 'venue': venue, 'days': days})
    return sorted(stale, key=lambda s: -s['days'])


def report(failed, stale):
    """failed: [(region, venue, error_text)] for scrapers that crashed this run."""
    for region, venue, error in failed:
        logging.error(f"Scraper crashed - [{region}] {venue}: {error}")
    for s in stale:
        logging.warning(f"Scraped data not refreshing - [{s['region']}] {s['venue']}: "
                        f"no update in {s['days']} days")
    logging.info(f"Finished scraper health check: {len(failed)} crashed, {len(stale)} stale venues")

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write(render_markdown(failed, stale))


def render_markdown(failed, stale):
    lines = ["## Scraper health", ""]
    if not failed and not stale:
        return "\n".join(lines + ["All scrapers ran and every venue is refreshing.", ""])
    if failed:
        lines += [f"### Crashed this run ({len(failed)})", ""]
        lines += [f"- `{region}` **{venue}**: {error}" for region, venue, error in failed]
        lines.append("")
    if stale:
        lines += [f"### Data not refreshing for over {STALE_AFTER_DAYS} days ({len(stale)})", "",
                  "Usually a blocked or redesigned site - the scraper logs an error and carries on.", ""]
        lines += [f"- `{s['region']}` **{s['venue']}**: last updated {s['days']} days ago" for s in stale]
        lines.append("")
    return "\n".join(lines)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    report([], find_stale_venues())
