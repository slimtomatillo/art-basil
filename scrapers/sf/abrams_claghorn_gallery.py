from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://abramsclaghornshop.com'
# The gallery runs a Shopify shop; the current show is a collection linked in the
# "Current Exhibit" menu, titled "<Show> | October 3-29, 2026" on its own page.
_TITLE_DATES_RE = re.compile(r'^(.+?)\s*\|\s*([A-Z][a-z]+ \d{1,2}\s*[-–—]\s*(?:[A-Z][a-z]+ )?\d{1,2},\s*\d{4})\s*$')


def scrape_abrams_claghorn_gallery(env='prod', region='sf'):
    """Scrape and process the current exhibit of Abrams Claghorn Gallery."""

    today = region_today(region)
    home = fetch_and_parse(BASE_URL + '/')
    if home is None:
        logging.warning("Abrams Claghorn Gallery: could not fetch the home page; existing data kept.")
        return

    link = None
    for a in home.find_all('a', href=True):
        if a['href'].startswith('/collections/') and 'Current Exhibit' not in a.get_text() and '|' in a.get_text():
            link = a
            break
    if link is None:
        logging.warning("Abrams Claghorn Gallery: no current exhibit link found; existing data kept.")
        return

    url = urljoin(BASE_URL, link['href'])
    soup = fetch_and_parse(url)
    if soup is None:
        return
    name = start_date = end_date = None
    for line in (l.strip() for l in soup.get_text('\n').split('\n')):
        m = _TITLE_DATES_RE.match(line)
        if m:
            name = m.group(1).strip()
            start_date, end_date = parse_date_text(m.group(2), today)
            break
    if not (name and start_date and end_date):
        logging.warning(f"Abrams Claghorn Gallery: no title and dates on {url}")
        return
    phase = derive_phase(start_date, end_date, today) or 'current'

    event_details = {
        'name': name,
        'venue': 'Abrams Claghorn Gallery',
        'description': None,
        'tags': ['exhibition'] + [phase] + ['gallery'],
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': False,
        'links': [{'link': url, 'description': 'Event Page'}],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if env == 'dev':
        logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
    if env == 'prod':
        process_event(event_details, region)
