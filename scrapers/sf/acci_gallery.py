from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://www.accigallery.com'
_MONTH_START_RE = re.compile(r'^(?:[A-Z][a-z]+,\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}')
_MAX_DESCRIPTION = 400


def scrape_acci_gallery(env='prod', region='sf'):
    """Scrape and process the current exhibition of ACCI Gallery, a member-run cooperative."""

    today = region_today(region)
    home = fetch_and_parse(BASE_URL + '/')
    if home is None:
        logging.warning("ACCI Gallery: could not fetch the home page; existing data kept.")
        return

    # The menu has a "Current Exhibition" group whose child link is the show's page
    label = home.find(string=re.compile(r'^\s*Current Exhibition\s*$'))
    link = None
    if label is not None:
        link = next((a for a in label.find_all_next('a', href=True)
                     if a['href'].endswith('.html') and a.get_text(strip=True) not in ('', '>')), None)
    if link is None:
        logging.warning("ACCI Gallery: no current exhibition link in the menu; existing data kept.")
        return

    name = link.get_text(' ', strip=True)
    url = urljoin(BASE_URL + '/', link['href'])
    soup = fetch_and_parse(url)
    if soup is None:
        return
    lines = [l.replace('​', '').replace('﻿', '').strip() for l in soup.get_text('\n').split('\n')]
    lines = [l for l in lines if l]
    # The date range is the first line after the title that opens with a (weekday and) month
    idx = next((i for i, l in enumerate(lines) if l == name), None)
    date_line = next((l for l in lines[(idx or 0) + 1:] if _MONTH_START_RE.match(l) and re.search(r'[-–—]', l)), None)
    if not date_line:
        logging.warning(f"ACCI Gallery: no date range for {name!r}")
        return
    start_date, end_date = parse_date_text(date_line, today)
    if not (start_date and end_date):
        logging.warning(f"ACCI Gallery: no readable dates for {name!r}")
        return
    phase = derive_phase(start_date, end_date, today) or 'current'
    meta = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
    description = ' '.join(meta['content'].split())[:_MAX_DESCRIPTION] if meta and meta.get('content') else None

    event_details = {
        'name': name,
        'venue': 'ACCI Gallery',
        'description': description,
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
