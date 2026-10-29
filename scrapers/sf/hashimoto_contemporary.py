from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from scrapers.sf._artlogic import artlogic_items, parse_day_first_range
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://www.hashimotocontemporary.com'
# One site covers the New York and San Francisco galleries; each listing names its location
PAGES = (BASE_URL + '/exhibitions/current/', BASE_URL + '/exhibitions/forthcoming/')


def scrape_hashimoto_contemporary(env='prod', region='sf'):
    """Scrape and process the San Francisco shows of Hashimoto Contemporary."""

    today = region_today(region)
    found = 0
    seen = set()
    for url in PAGES:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Hashimoto Contemporary: could not fetch {url}; existing data kept.")
            continue
        for item in artlogic_items(soup, BASE_URL):
            if item['location'].strip().upper().endswith('NYC') or 'SF' not in item['location'].upper().split():
                continue
            if item['link'] in seen:
                continue
            seen.add(item['link'])
            start_date, end_date = parse_day_first_range(item['date_text'])
            if not (start_date and end_date):
                logging.warning(f"Hashimoto Contemporary: no readable dates for {item['name']!r}")
                continue
            phase = derive_phase(start_date, end_date, today) or 'current'
            if phase == 'past':
                continue
            event_details = {
                'name': item['name'],
                'venue': 'Hashimoto Contemporary',
                'description': item['description'],
                'tags': ['exhibition'] + [phase] + ['gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': item['link'], 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            found += 1
            if env == 'dev':
                logging.info(f"Event found: {item['name']} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
            if env == 'prod':
                process_event(event_details, region)

    if not found:
        logging.warning("Hashimoto Contemporary: no San Francisco shows found; existing data kept.")
