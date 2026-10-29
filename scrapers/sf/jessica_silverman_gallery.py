from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

EXHIBITIONS_URL = 'https://jessicasilvermangallery.com/exhibitions/'

# The page's sliders also list art fairs and museum shows; only the gallery's
# own shows (current + upcoming) are wanted, and fairs name a booth or fair.
_FAIR_RE = re.compile(r'art basel|adaa|fog design|frieze|armory|art fair|booth|expo chicago|the shed|art cologne', re.I)


def scrape_jessica_silverman_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Jessica Silverman."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Jessica Silverman: could not fetch the exhibitions page; existing data kept.")
        return

    found = 0
    seen = set()
    for card in soup.select('div.exhibition'):
        # Past shows live in their own slider and archive
        slider = card.find_parent(id=True)
        if slider is not None and 'past' in slider['id']:
            continue
        title_tag = card.find('h3')
        date_tag = card.find('h4')
        link_tag = card.find('a', href=True)
        if not (title_tag and date_tag and link_tag):
            continue
        name = ' '.join(title_tag.get_text().split())
        if _FAIR_RE.search(name) or name in seen:
            continue
        start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue
        seen.add(name)

        event_details = {
            'name': name,
            'venue': 'Jessica Silverman Gallery',
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
        logging.warning("Jessica Silverman: no exhibitions found; existing data kept.")
