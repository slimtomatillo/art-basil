from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://www.traywick.com'
EXHIBITIONS_URL = BASE_URL + '/exhibitions/'

# Only dates with a day number count; "December 2025 - January 2026" would otherwise be read as a day 20 and 20
_DAY_DATE_RE = re.compile(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b')


def scrape_traywick_contemporary(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Traywick Contemporary."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Traywick Contemporary: could not fetch the exhibitions page; existing data kept.")
        return

    found = 0
    for card in soup.select('div.grid-item-content'):
        link_tag = card.select_one('h2 a[href]')
        date_tag = card.find('p', style=True)
        if not (link_tag and date_tag):
            continue
        name = link_tag.get_text(' ', strip=True)
        # The archive back to 2017 is listed too, some with loose dates ("Continues through
        # Summer, 2026") that parse_date_text can't read; those are skipped
        date_text = date_tag.get_text(' ', strip=True)
        if not _DAY_DATE_RE.search(date_text):
            continue
        start_date, end_date = parse_date_text(date_text, today)
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue

        event_details = {
            'name': name,
            'venue': 'Traywick Contemporary',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': urljoin(BASE_URL, link_tag['href']), 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("Traywick Contemporary: no current or upcoming exhibitions found; existing data kept.")
