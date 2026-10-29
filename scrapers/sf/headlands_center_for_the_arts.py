from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

WHATS_ON_URL = 'https://www.headlands.org/whats-on/'

# Public shows are the installations and exhibitions (the page also lists monthly
# dinners and permanent installations). Dates read like "Sept 20–Nov 16, Thursday–Sunday, 12–5PM".
_SHOW_TYPES = {'installation', 'exhibition'}
_RANGE_RE = re.compile(r'^([A-Za-z]+\.?\s+\d{1,2}\s*[–-]\s*(?:[A-Za-z]+\.?\s+)?\d{1,2}(?:,\s*\d{4})?)')


def scrape_headlands_center_for_the_arts(env='prod', region='sf'):
    """Scrape and process the public installations and exhibitions at Headlands Center for the Arts."""

    today = region_today(region)
    soup = fetch_and_parse(WHATS_ON_URL)
    if soup is None:
        logging.warning("Headlands: could not fetch the What's On page; existing data kept.")
        return

    found = 0
    seen = set()
    for block in soup.select('div.listing-block--event'):
        if block.get('data-event-type') not in _SHOW_TYPES:
            continue
        title_tag = block.select_one('.event-title')
        date_tag = block.select_one('.event-date')
        link_tag = block.select_one('a.screen-link[href]')
        if not (title_tag and date_tag and link_tag):
            continue
        name = ' '.join(title_tag.get_text().split())
        m = _RANGE_RE.match(' '.join(date_tag.get_text().split()))
        if not m or name in seen:
            continue
        start_date, end_date = parse_date_text(m.group(1), today)
        if not (start_date and end_date):
            continue
        seen.add(name)
        phase = derive_phase(start_date, end_date, today) or 'current'

        event_details = {
            'name': name,
            'venue': 'Headlands Center for the Arts',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': link_tag['href'], 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("Headlands: no installations or exhibitions with dates found; existing data kept.")
