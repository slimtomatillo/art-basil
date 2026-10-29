from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
import datetime as dt
from datetime import timezone
from zoneinfo import ZoneInfo
import json
import logging
import re

HOME_URL = 'https://www.helvella.art/'
EVENT_URL = 'https://www.helvella.art/event-details/'

# The site is Wix; its events widget embeds each event as JSON in the page
# (title, slug, and a scheduling block with UTC start/end instants).
_EVENT_RE = re.compile(r'"title":"((?:[^"\\]|\\.)*)","description":"((?:[^"\\]|\\.)*)","about":"[^"]*","mainImage"')
_SLUG_RE = re.compile(r'"slug":"([^"]+)"')
_SCHEDULE_RE = re.compile(r'"startDate":"([^"]+)","endDate":"([^"]+)"')
_TZ_RE = re.compile(r'"timeZoneId":"([^"]+)"')
_MAX_DESCRIPTION = 400


def _local_date(iso, tz):
    return dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(tz).date()


def scrape_helvella_art(env='prod', region='sf'):
    """Scrape and process the events and past exhibitions of Helvella Art."""

    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Helvella Art: could not fetch the home page; existing data kept.")
        return
    html = str(soup)

    found, seen = 0, set()
    for m in _EVENT_RE.finditer(html):
        # Within an event object the scheduling block comes before the title and the slug after it
        slug = _SLUG_RE.search(html, m.end(), m.end() + 1500)
        before = html[max(0, m.start() - 2500):m.start()]
        schedules = _SCHEDULE_RE.findall(before)
        if not (slug and schedules) or slug.group(1) in seen:
            continue
        seen.add(slug.group(1))
        schedule = schedules[-1]
        tz_match = _TZ_RE.findall(before)
        tz_match = tz_match[-1] if tz_match else None
        tz = ZoneInfo(tz_match.replace('\\/', '/') if tz_match else 'America/Los_Angeles')
        name = json.loads('"' + m.group(1) + '"')
        description = json.loads('"' + m.group(2) + '"') or None
        start_date = _local_date(schedule[0], tz)
        end_date = _local_date(schedule[1], tz)
        phase = derive_phase(start_date, end_date, today) or 'current'

        kind = 'event' if re.search(r'open studio', name, re.I) else 'exhibition'
        event_details = {
            'name': name,
            'venue': 'Helvella Art',
            'description': description[:_MAX_DESCRIPTION] if description else None,
            'tags': [kind] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': EVENT_URL + slug.group(1), 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({kind}, {phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("Helvella Art: no events found; existing data kept.")
