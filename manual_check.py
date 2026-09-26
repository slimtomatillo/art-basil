"""Check manually-entered events for anything that needs a human update.

Events added by hand (see SUBMISSIONS.md) carry "source": "manual". Nothing
refreshes them, so this runs after the daily scrape and reports:

- venues whose last listed show is about to end (or just ended), so the next
  exhibition gets added
- events whose page is gone, or no longer mentions the event's title
- events whose page can't be checked because the site blocks automated requests

Findings go to the log and, in GitHub Actions, the run summary. Run it on its
own with `python manual_check.py`.
"""

import datetime as dt
import logging
import os
import re
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from config import DB_FILES
from utils import load_db

MANUAL_SOURCE = 'manual'
ENDING_SOON_DAYS = 14   # last listed show ends within this many days
RECENTLY_ENDED_DAYS = 30  # ...or ended within this many days
TITLE_MATCH_THRESHOLD = 0.6
BLOCKED_STATUSES = {401, 403, 429, 503}
REQUEST_TIMEOUT = 20
HEADERS = {'User-Agent': 'Your Bot 0.1'}


def _parse(date_str):
    return dt.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None


def _tokens(text):
    text = (text or '').casefold().replace('’', "'").replace('‘', "'")
    return {t for t in re.findall(r"\w+", text) if len(t) >= 3}


def title_on_page(title, page_text):
    """True if most of the title's words appear on the page (case/punctuation-insensitive)."""
    wanted = _tokens(title)
    if not wanted:
        return True
    return len(wanted & _tokens(page_text)) / len(wanted) >= TITLE_MATCH_THRESHOLD


def load_manual_events():
    """Return [(region, venue, event)] for every manually-entered event."""
    found = []
    for region, path in DB_FILES.items():
        for venue, events in load_db(path).items():
            for event in events.values():
                if event.get('source') == MANUAL_SOURCE:
                    found.append((region, venue, event))
    return found


def check_venue_lifecycles(manual, today):
    """Flag venues whose latest manual show is ending soon or just ended."""
    latest_end = {}
    for region, venue, event in manual:
        end = _parse(event['dates'].get('end'))
        if end and (not latest_end.get((region, venue)) or end > latest_end[(region, venue)]):
            latest_end[(region, venue)] = end

    findings = []
    for (region, venue), end in sorted(latest_end.items()):
        days_left = (end - today).days
        if -RECENTLY_ENDED_DAYS <= days_left <= ENDING_SOON_DAYS:
            when = f"ends {end}" if days_left >= 0 else f"ended {end}"
            findings.append({
                'kind': 'action', 'region': region, 'venue': venue, 'event': None,
                'message': f"last listed show {when}; check the venue for its next exhibition",
            })
    return findings


def check_event_page(region, venue, event):
    """Return a finding for an event whose page looks wrong or can't be checked, else None."""
    links = [l['link'] for l in event.get('links', []) if l.get('description') == 'Event Page']
    if not links:
        return None
    url = links[0]
    base = {'region': region, 'venue': venue, 'event': event['name']}

    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        return {**base, 'kind': 'action', 'message': f"page unreachable ({type(e).__name__}): {url}"}

    if response.status_code in (404, 410):
        return {**base, 'kind': 'action', 'message': f"event page is gone (HTTP {response.status_code}): {url}"}
    if response.status_code in BLOCKED_STATUSES or response.headers.get('x-vercel-mitigated'):
        return {**base, 'kind': 'info', 'message': f"can't verify automatically (site blocks bots, HTTP {response.status_code}): {url}"}
    if response.status_code >= 400:
        return {**base, 'kind': 'action', 'message': f"event page returned HTTP {response.status_code}: {url}"}

    page_text = BeautifulSoup(response.content, 'html.parser').get_text(' ', strip=True)
    if not title_on_page(event['name'], page_text):
        return {**base, 'kind': 'action',
                'message': f"title no longer found on the page (changed, or JS-rendered): {url}"}
    return None


def check_manual_events(today=None):
    """Run every check; returns a list of findings ({kind: 'action'|'info', ...})."""
    today = today or dt.date.today()
    manual = load_manual_events()
    findings = check_venue_lifecycles(manual, today)

    for region, venue, event in manual:
        end = _parse(event['dates'].get('end'))
        if end and end < today:
            continue  # nothing to verify on an event that's already over
        finding = check_event_page(region, venue, event)
        time.sleep(0.5)
        if finding:
            findings.append(finding)

    report(findings, len(manual))
    return findings


def report(findings, total):
    actions = [f for f in findings if f['kind'] == 'action']
    infos = [f for f in findings if f['kind'] == 'info']

    for f in actions:
        subject = f"{f['venue']}: {f['event']}" if f['event'] else f['venue']
        logging.warning(f"Manual event needs review - [{f['region']}] {subject} - {f['message']}")
    logging.info(f"Finished manual-event check: {total} manual events, "
                 f"{len(actions)} to review, {len(infos)} unverifiable")

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write(render_markdown(actions, infos, total))


def render_markdown(actions, infos, total):
    lines = [f"## Manual events ({total} tracked)", ""]
    if not actions:
        lines += ["Nothing needs review.", ""]
    else:
        lines += [f"### Needs review ({len(actions)})", ""]
        for f in actions:
            subject = f"**{f['venue']}** - {f['event']}" if f['event'] else f"**{f['venue']}**"
            lines.append(f"- `{f['region']}` {subject}: {f['message']}")
        lines.append("")
    if infos:
        by_venue = defaultdict(list)
        for f in infos:
            by_venue[(f['region'], f['venue'])].append(f)
        lines += ["### Can't be verified automatically", ""]
        for (region, venue), items in sorted(by_venue.items()):
            lines.append(f"- `{region}` **{venue}**: {len(items)} event(s) - {items[0]['message'].split(':')[0]}")
        lines.append("")
    return "\n".join(lines)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    check_manual_events()
