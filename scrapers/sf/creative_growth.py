from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging

EXHIBITIONS_URL = 'https://creativegrowth.org/exhibitions'


def scrape_creative_growth(env='prod', region='sf'):
    """Scrape and process the exhibition(s) shown on the Creative Growth exhibitions page."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Creative Growth: could not fetch the exhibitions page; existing data kept.")
        return

    # The page is a flat run of text blocks: a title (h1) directly followed by
    # its date range (h2). Only titles whose next block reads as a date range count.
    blocks = soup.select('span[data-heading="h1"], span[data-heading="h2"]')
    found = 0
    for i, block in enumerate(blocks[:-1]):
        nxt = blocks[i + 1]
        if block['data-heading'] != 'h1' or nxt['data-heading'] != 'h2':
            continue
        name = block.get_text(' ', strip=True)
        start_date, end_date = parse_date_text(nxt.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'

        event_details = {
            'name': name,
            'venue': 'Creative Growth Art Center',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': EXHIBITIONS_URL, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
        # Only the lead block is the show at the Oakland gallery; the blocks below it
        # are off-site fairs and past presentations.
        break

    if not found:
        logging.warning("Creative Growth: no exhibitions found; existing data kept.")
