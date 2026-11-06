"""Track which events have no picture of their own, so they can be revisited.

An event is in one of three states, judged on current and upcoming events only:
  own   - it has an "Image" link (from its scraper or from images.py);
  logo  - no picture of its own, but its venue has a logo in docs/data/venue_images.json, which the
          table shows instead;
  none  - nothing at all, so the table cell is blank.

Every daily run (main.py) rewrites IMAGE_AUDIT.md, which lists the venues with events in the last
two states, and adds the same summary to the GitHub Actions job summary. The file is committed with
the data, so its history shows the coverage changing over time.

Nothing here fetches anything. Events with no picture are retried automatically by images.py every
RECHECK_AFTER (14 days) and scrapers look again on every run; the audit says which venues still need
a person: a better scraper, or a logo added to venue_images.json.

Print it any time:  python image_audit.py
"""

import datetime as dt
import json
import logging
import os

from config import DB_FILES
from images import WANTED_PHASES, event_page, image_link
from utils import load_db

REPORT_PATH = 'IMAGE_AUDIT.md'
VENUE_IMAGES_FILE = 'venue_images.json'


def load_venue_images(region):
    """{venue: logo url} from the venue_images.json beside the region's event file."""
    path = os.path.join(os.path.dirname(DB_FILES[region]), VENUE_IMAGES_FILE)
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def collect(regions=None):
    """{(region, venue): {'total', 'own', 'logo', 'none', 'missing': [event info]}} for every
    venue with current or upcoming events. `missing` lists the events with no picture of their own."""
    result = {}
    for region in (regions or DB_FILES):
        logos = load_venue_images(region)
        for venue, events in load_db(DB_FILES[region]).items():
            wanted = [e for e in events.values() if e.get('phase') in WANTED_PHASES]
            if not wanted:
                continue
            row = {'total': len(wanted), 'own': 0, 'logo': 0, 'none': 0, 'missing': []}
            for event in wanted:
                if image_link(event):
                    row['own'] += 1
                    continue
                state = 'logo' if venue in logos else 'none'
                row[state] += 1
                row['missing'].append({'name': event['name'], 'state': state, 'page': event_page(event),
                                       'checked': event.get('image_checked'), 'source': event.get('source')})
            result[(region, venue)] = row
    return result


def totals(audit):
    keys = ('total', 'own', 'logo', 'none')
    return {k: sum(row[k] for row in audit.values()) for k in keys}


def render_markdown(audit, today=None, details=True):
    today = today or dt.date.today()
    t = totals(audit)
    share = (100 * t['own'] / t['total']) if t['total'] else 0
    lines = ["## Event pictures", "",
             f"Current and upcoming events on {today.isoformat()}: **{t['total']}**. "
             f"With their own picture: **{t['own']}** ({share:.0f}%). "
             f"Showing the venue's logo instead: **{t['logo']}**. No picture at all: **{t['none']}**.", ""]
    needing = {k: row for k, row in audit.items() if row['missing']}
    if not needing:
        return "\n".join(lines + ["Every event has a picture of its own.", ""])
    lines += ["Venues with events that have no picture of their own, most first. Worth a look now and "
              "then: the venue may have a better picture on its site, or its scraper may need to read "
              "one (see OPERATIONS.md, \"Event images\").", "",
              "| Region | Venue | Events | Own picture | Logo | None |",
              "|---|---|---:|---:|---:|---:|"]
    ordered = sorted(needing.items(), key=lambda kv: (-(kv[1]['logo'] + kv[1]['none']), kv[0]))
    for (region, venue), row in ordered:
        lines.append(f"| `{region}` | {venue} | {row['total']} | {row['own']} | {row['logo']} | {row['none']} |")
    lines.append("")
    if details:
        lines += ["### Events without a picture of their own", ""]
        for (region, venue), row in ordered:
            lines.append(f"**{venue}** (`{region}`)")
            lines.append("")
            for e in row['missing']:
                title = f"[{e['name']}]({e['page']})" if e['page'] else e['name']
                shown = "venue logo" if e['state'] == 'logo' else "blank"
                checked = f"page last checked {e['checked']}" if e['checked'] else "page not checked yet"
                extra = " (entered by hand)" if e['source'] == 'manual' else ""
                lines.append(f"- {title}: {shown}; {checked}{extra}")
            lines.append("")
    return "\n".join(lines)


def write_report(today=None, regions=None, path=REPORT_PATH):
    """Rewrite IMAGE_AUDIT.md and add the summary (no event list) to the Actions job summary.
    Returns the totals."""
    audit = collect(regions)
    today = today or dt.date.today()
    with open(path, 'w') as f:
        f.write("# Event picture audit\n\nWritten by `image_audit.py` on every daily run; do not edit by hand.\n\n")
        f.write(render_markdown(audit, today))
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write(render_markdown(audit, today, details=False))
    t = totals(audit)
    logging.info(f"Finished image audit: {t['own']} of {t['total']} current/upcoming events have their own picture, "
                 f"{t['logo']} use a venue logo, {t['none']} have none")
    return t


if __name__ == '__main__':
    print(render_markdown(collect()))
