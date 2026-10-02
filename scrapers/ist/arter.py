from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re
import time

import requests
from urllib.parse import quote

BASE_URL = 'https://www.arter.org.tr'
# The exhibitions page fills itself from three ASP.NET page methods (current /
# next / previous). The "_en" variants return English titles and dates.
API_URL = f'{BASE_URL}/EventType_en.aspx'
EXHIBITIONS_CATEGORY_ID = 1
# The API returns the first N events, newest first; the whole archive is ~85.
MAX_EVENTS = 500

# Past shows go back to 2010; only keep roughly the last two years.
PAST_WINDOW_DAYS = 730
MAX_DESCRIPTION_CHARS = 500

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# "Until 15 November 2026", "As of 8 October 2026"
UNTIL_RE = re.compile(rf'^until\s+(?P<d>\d{{1,2}})\s+(?P<m>{MONTH_RE})\s+(?P<y>\d{{4}})$', re.IGNORECASE)
AS_OF_RE = re.compile(rf'^as of\s+(?P<d>\d{{1,2}})\s+(?P<m>{MONTH_RE})\s+(?P<y>\d{{4}})$', re.IGNORECASE)
# "11.09.2025-10.03.2026", "27.11.2025 – 12.04.2026" (day.month.year)
NUMERIC_RANGE_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[–—-]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})$')
# "3 March - 4 June 2025", "3 March 2025 - 4 June 2025"
WORDS_RANGE_RE = re.compile(
    rf'^(?P<d1>\d{{1,2}})\s+(?P<m1>{MONTH_RE})(?:\s+(?P<y1>\d{{4}}))?\s*[–—-]\s*'
    rf'(?P<d2>\d{{1,2}})\s+(?P<m2>{MONTH_RE})\s+(?P<y2>\d{{4}})$',
    re.IGNORECASE
)


def parse_dates(text):
    """Return (start_date, end_date); either can be None ("Until ..." has no start, "As of ..." no end)."""
    text = ' '.join(text.replace('\xa0', ' ').split())
    try:
        match = UNTIL_RE.match(text)
        if match:
            return None, dt.date(int(match.group('y')), MONTH_TO_NUM_DICT[match.group('m').lower()],
                                 int(match.group('d')))
        match = AS_OF_RE.match(text)
        if match:
            return dt.date(int(match.group('y')), MONTH_TO_NUM_DICT[match.group('m').lower()],
                           int(match.group('d'))), None
        match = NUMERIC_RANGE_RE.match(text)
        if match:
            d1, m1, y1, d2, m2, y2 = (int(g) for g in match.groups())
            return dt.date(y1, m1, d1), dt.date(y2, m2, d2)
        match = WORDS_RANGE_RE.match(text)
        if match:
            y2 = int(match.group('y2'))
            end_date = dt.date(y2, MONTH_TO_NUM_DICT[match.group('m2').lower()], int(match.group('d2')))
            y1 = int(match.group('y1')) if match.group('y1') else y2
            start_date = dt.date(y1, MONTH_TO_NUM_DICT[match.group('m1').lower()], int(match.group('d1')))
            if start_date > end_date and not match.group('y1'):
                start_date = start_date.replace(year=start_date.year - 1)
            return start_date, end_date
    except ValueError:
        pass
    logging.warning(f"Arter: could not parse dates {text!r}")
    return None, None


def fetch_events(method):
    """POST to one of the page methods; returns its list of events ([] on failure)."""
    try:
        response = requests.post(
            f'{API_URL}/{method}',
            data=f'{{dataCount:{MAX_EVENTS},CategoryID:{EXHIBITIONS_CATEGORY_ID}}}',
            headers={'User-Agent': 'Your Bot 0.1', 'Content-Type': 'application/json; charset=utf-8'},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get('d') or []
    except (requests.RequestException, ValueError) as e:
        logging.error(f"Error fetching Arter {method}: {e}")
        return []


def fetch_description(event_link):
    """The listing only carries the curator line; the detail page has the actual text."""
    soup = fetch_and_parse(event_link)
    time.sleep(0.5)
    if soup is None:
        return None
    desc = soup.select_one('.detail-desc')
    if desc is None:
        return None
    text = ' '.join(desc.get_text(' ', strip=True).split())
    if len(text) > MAX_DESCRIPTION_CHARS:
        text = text[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'
    return text or None


def scrape_arter_exhibitions(env='prod', region='ist'):
    """Scrape and process current, upcoming and recent past exhibitions from Arter."""

    sections = [('LoadCurrentEvents', 'current'), ('LoadNextEvents', 'future'), ('LoadPreviousEvents', 'past')]
    listings = [(phase, fetch_events(method)) for method, phase in sections]
    if not any(events for _, events in listings):
        logging.warning("Arter: no exhibitions found")
        return

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)

    seen = set()
    for section_phase, events in listings:
        for event in events:
            if event['EventID'] in seen:
                continue
            seen.add(event['EventID'])

            title = ' '.join(event['EventHeaderEN'].split())
            start_date, end_date = parse_dates(event['EventDatesEN'])

            if end_date and end_date < today:
                if end_date < cutoff:
                    continue
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            elif start_date or end_date:
                phase = 'current'
            else:
                phase = section_phase

            # "As of <date>" with no closing date marks an open-ended show
            ongoing = bool(start_date and not end_date and start_date <= today)

            event_link = f"{BASE_URL}/EN/{event['CategoryNameEN2']}/{event['EventHeaderURL']}/{event['EventID']}"
            description = fetch_description(event_link)

            event_details = {
                'name': title,
                'venue': 'Arter',
                'description': description,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            image = event.get('EventListImageFile')
            if image:
                image_url = image if image.startswith('http') else BASE_URL + quote(image, safe='/()')
                event_details['links'].append({'link': image_url, 'description': 'Image'})

            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            if env == 'prod':
                process_event(event_details, region)
