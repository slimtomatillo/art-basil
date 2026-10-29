from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging

HOME_URL = 'https://mercurytwenty.com/'


def scrape_mercury_20_gallery(env='prod', region='sf'):
    """Scrape and process the current exhibitions listed on the Mercury 20 Gallery home page."""

    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Mercury 20 Gallery: could not fetch the home page; existing data kept.")
        return

    found = 0
    # Each show is a heading, a "View the Exhibition" button and an h4 date range
    for title_tag in soup.select('h3.elementor-heading-title'):
        container = title_tag.find_parent(class_='e-con')
        link_tag = container.select_one('a[href*="/exhibition/"]') if container else None
        date_tag = container.find('h4') if container else None
        if not (link_tag and date_tag):
            continue
        name = title_tag.get_text(' ', strip=True)
        start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            logging.warning(f"Mercury 20 Gallery: no readable dates for {name!r}")
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'

        event_details = {
            'name': name,
            'venue': 'Mercury 20 Gallery',
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
        logging.warning("Mercury 20 Gallery: no exhibitions found; existing data kept.")
