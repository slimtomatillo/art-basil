from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
import datetime as dt
from datetime import timezone
import logging
import re

EXHIBITIONS_URL = 'https://svma.org/exhibitions/'

# Current, Upcoming and Past sit on one page, with the Past archive running
# back to 2011; only the most recent past shows are worth re-scraping daily.
MAX_PAST = 15

_DATE_RANGE_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{2})\s*-\s*(\d{2})\.(\d{2})\.(\d{2})')
_BG_IMAGE_RE = re.compile(r'url\(([^)]+)\)')

def parse_date_range(text):
    """SVMA writes ranges as 'MM.DD.YY - MM.DD.YY' (sometimes with a prose
    version or an 'Online:' prefix in front, so search rather than match)."""
    m = _DATE_RANGE_RE.search(text)
    if not m:
        return None, None
    m1, d1, y1, m2, d2, y2 = (int(g) for g in m.groups())
    return dt.date(2000 + y1, m1, d1), dt.date(2000 + y2, m2, d2)

def scrape_svma(env='prod', region='sf'):
    """Scrape and process exhibitions from the Sonoma Valley Museum of Art."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("SVMA: could not fetch the exhibitions page; existing data kept.")
        return

    for section_class, tab_phase in (('current', 'current'), ('upcoming', 'future'), ('past', 'past')):
        section = soup.select_one(f'section.slice.{section_class}')
        if not section:
            logging.warning(f"SVMA: '{section_class}' section not found")
            continue
        cards = section.select('div.card')
        if tab_phase == 'past':
            cards = cards[:MAX_PAST]

        for card in cards:
            title_tag = card.select_one('.card-title')
            link_tag = card.find('a', href=True)
            range_tag = card.select_one('.range')
            if not title_tag or not link_tag or not range_tag:
                continue

            name = title_tag.get_text(' ', strip=True).replace('\xa0', ' ')
            start_date, end_date = parse_date_range(range_tag.get_text(' ', strip=True))
            if not (start_date or end_date):
                logging.warning(f"SVMA: could not parse dates {range_tag.get_text(strip=True)!r} for {name!r}")
                continue

            phase = derive_phase(start_date, end_date, today) or tab_phase

            image_div = card.select_one('.image')
            bg = _BG_IMAGE_RE.search(image_div.get('style', '')) if image_div else None
            image_link = bg.group(1).strip('\'"') if bg else None

            event_details = {
                'name': name,
                'venue': 'Sonoma Valley Museum of Art',
                'description': None,
                'tags': ['exhibition'] + [phase] + ['museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': link_tag['href'], 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'dev':
                logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
            if env == 'prod':
                process_event(event_details, region)
