from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://www.thelmaharrisartgallery.com'
EXHIBITIONS_URL = BASE_URL + '/exhibitions'

# The exhibitions page lists "Current and upcoming exhibitions" above a
# "Past events and exhibitions" archive (back to 2014, most without dates).
# Only the first section is read; each show's own page carries a line like
# "August 22, 2026 - October 25, 2026".
_PAST_HEADING = 'past events and exhibitions'
_NAV_PATHS = {'/', '/gallery', '/blog', '/in-the-media', '/artists', '/events', '/exhibitions',
              '/cart', '/story', '/visit'}
_RANGE_RE = re.compile(r'^[A-Z][a-z]+\.?\s+\d{1,2},\s*\d{4}\s*[-–—]\s*[A-Z][a-z]+\.?\s+\d{1,2},\s*\d{4}$')
_MAX_DESCRIPTION = 400


def _current_links(soup):
    """Links of the shows above the 'Past events and exhibitions' heading."""
    hrefs = []
    for node in soup.find_all(['a', 'h1', 'h2', 'h3', 'h4', 'p', 'strong']):
        if node.name != 'a':
            if _PAST_HEADING in node.get_text(' ', strip=True).lower():
                break
            continue
        href = node.get('href', '')
        if not href.startswith('/') or href in _NAV_PATHS or href.startswith(('/photos', '/past-exhibitions', '//')):
            continue
        if href not in hrefs:
            hrefs.append(href)
    return hrefs


def scrape_thelma_harris_art_gallery(env='prod', region='sf'):
    """Scrape and process the current exhibitions of the Thelma Harris Art Gallery."""

    today = region_today(region)
    listing = fetch_and_parse(EXHIBITIONS_URL)
    if listing is None:
        logging.warning("Thelma Harris Art Gallery: could not fetch the exhibitions page; existing data kept.")
        return

    found = 0
    for href in _current_links(listing):
        url = urljoin(BASE_URL, href)
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        lines = [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()]
        date_line = next((l for l in lines if _RANGE_RE.match(l)), None)
        if not date_line:
            logging.warning(f"Thelma Harris Art Gallery: no date range on {url}")
            continue
        start_date, end_date = parse_date_text(date_line, today)
        if not (start_date and end_date):
            continue
        og = soup.find('meta', property='og:title')
        title = og['content'] if og and og.get('content') else (soup.title.get_text(strip=True) if soup.title else '')
        name = re.split(r'\s+[—–|-]\s+Thelma Harris', title)[0].strip()
        if not name:
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        meta = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        description = ' '.join(meta['content'].split())[:_MAX_DESCRIPTION] if meta and meta.get('content') else None

        event_details = {
            'name': name,
            'venue': 'Thelma Harris Art Gallery',
            'description': description,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': url, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("Thelma Harris Art Gallery: no exhibitions found; existing data kept.")
