from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging

EXHIBITIONS_URL = 'https://fraenkelgallery.com/exhibitions'


def scrape_fraenkel_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming gallery shows of Fraenkel Gallery."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Fraenkel Gallery: could not fetch the exhibitions page; existing data kept.")
        return

    found = 0
    seen = set()
    for card in soup.select('article.fraenkel_exhibition'):
        classes = card.get('class', [])
        # "Gallery" shows only: the page also lists online "deep dives" of the same show,
        # art fairs and film festivals
        if 'exhibition_type-gallery' not in classes or 'exhibition_type-online' in classes:
            continue
        link_tag = card.select_one('.entry-title a[href]')
        artist_tag = card.select_one('.rel-artist')
        date_tag = card.select_one('.meta--exhibition-dates')
        if not (link_tag and date_tag):
            continue
        full = link_tag.get_text(' ', strip=True).replace(' :', ':')
        name = full
        if link_tag['href'] in seen:
            continue
        start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue
        seen.add(link_tag['href'])

        event_details = {
            'name': name,
            'venue': 'Fraenkel Gallery',
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
        logging.warning("Fraenkel Gallery: no exhibitions found; existing data kept.")
