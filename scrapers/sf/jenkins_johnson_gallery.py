from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from scrapers.sf._artlogic import artlogic_items, parse_day_first_range
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://www.jenkinsjohnsongallery.com'
EXHIBITIONS_URL = BASE_URL + '/exhibitions'


def scrape_jenkins_johnson_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Jenkins Johnson Gallery."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Jenkins Johnson Gallery: could not fetch the exhibitions page; existing data kept.")
        return

    found = 0
    for item in artlogic_items(soup, BASE_URL):
        start_date, end_date = parse_day_first_range(item['date_text'])
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        # The page also lists the archive back several years
        if phase == 'past':
            continue
        event_details = {
            'name': item['name'],
            'venue': 'Jenkins Johnson Gallery',
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
        logging.warning("Jenkins Johnson Gallery: no exhibitions found; existing data kept.")
