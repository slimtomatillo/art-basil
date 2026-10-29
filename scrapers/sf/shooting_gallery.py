from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

CALENDAR_URL = 'https://shootinggallerysf.com/events/'

# The Calendar of Events page lists each show as three lines: a date range,
# the show title, then the artist ("September 13th - October 4th, 2026").
# (The home page of this site has had spam links injected, so only /events/ is read.)
_RANGE_LINE_RE = re.compile(
    r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?\s*[-–—]\s*.*\d')
_SKIP_LINES = ('download press release',)


def scrape_shooting_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Shooting Gallery."""

    today = region_today(region)
    soup = fetch_and_parse(CALENDAR_URL)
    if soup is None:
        logging.warning("Shooting Gallery: could not fetch the calendar page; existing data kept.")
        return

    lines = [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()]
    found = 0
    last_year = None
    for i, line in enumerate(lines[:-1]):
        if not _RANGE_LINE_RE.match(line):
            continue
        # Some entries drop the year ("March 14th - April 4th"); the page runs in order, so
        # they take the year of the entry above rather than being guessed from today's date
        year = re.search(r'\b(20\d\d)\b', line)
        if year:
            last_year = year.group(1)
        elif last_year:
            line = f'{line}, {last_year}'
        start_date, end_date = parse_date_text(line, today)
        if not (start_date and end_date):
            continue
        name = lines[i + 1]
        artist = lines[i + 2] if i + 2 < len(lines) and lines[i + 2].lower() not in _SKIP_LINES else None
        if name.lower() in _SKIP_LINES:
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue
        if artist and artist.lower() not in name.lower():
            name = f'{name} - {artist}'

        event_details = {
            'name': name,
            'venue': 'Shooting Gallery',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': CALENDAR_URL, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("Shooting Gallery: no current or upcoming shows found; existing data kept.")
