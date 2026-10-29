from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

PAGE_URL = 'https://www.elcerrito.gov/95/City-Hall-Gallery-Space'

# The page's "Current Exhibit" block reads, once its lines are joined:
#   "<Title>, by <Artist> ... September 19 - October 16, 2026 EXTENDED to December 11, 2026 Artist's Reception: ..."
_EXHIBIT_RE = re.compile(
    r'^(?P<title>.+?)\s+(?P<start>[A-Z][a-z]+\s+\d{1,2})\s*-\s*(?P<end>[A-Z][a-z]+\s+\d{1,2},\s*\d{4})'
    r'(?:\s+EXTENDED to (?P<extended>[A-Z][a-z]+\s+\d{1,2},\s*\d{4}))?')


def scrape_el_cerrito_city_hall_gallery(env='prod', region='sf'):
    """Scrape and process the current exhibit in the El Cerrito City Hall gallery."""

    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("El Cerrito City Hall Gallery: could not fetch the page; existing data kept.")
        return

    lines = [' '.join(l.split()) for l in soup.get_text('\n').split('\n')]
    lines = [l for l in lines if l]
    try:
        start_idx = lines.index('Current Exhibit')
    except ValueError:
        logging.warning("El Cerrito City Hall Gallery: no 'Current Exhibit' block found; existing data kept.")
        return
    end_idx = next((i for i in range(start_idx + 1, len(lines)) if lines[i].startswith(('Past Exhibits', 'Artist\'s Reception'))), start_idx + 12)
    block = ' '.join(lines[start_idx + 1:end_idx])
    m = _EXHIBIT_RE.match(block)
    if not m:
        logging.warning("El Cerrito City Hall Gallery: could not read the current exhibit; existing data kept.")
        return

    name = re.sub(r'\s+,', ',', m.group('title')).strip(' ,')
    start_date, end_date = parse_date_text(f"{m.group('start')} - {m.group('end')}", today)
    if m.group('extended'):
        # The run was extended past the printed end date
        _, extended_end = parse_date_text(f"{m.group('start')} - {m.group('extended')}", today)
        end_date = extended_end or end_date
    if not (start_date and end_date):
        logging.warning(f"El Cerrito City Hall Gallery: no readable dates for {name!r}")
        return
    phase = derive_phase(start_date, end_date, today) or 'current'

    event_details = {
        'name': name,
        'venue': 'El Cerrito City Hall Gallery',
        'description': None,
        'tags': ['exhibition'] + [phase] + ['gallery'],
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': False,
        'links': [{'link': PAGE_URL, 'description': 'Event Page'}],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if env == 'dev':
        logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
    if env == 'prod':
        process_event(event_details, region)
