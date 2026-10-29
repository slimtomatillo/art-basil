from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://thetransmissiongallery.com'

# Each show has its own page; its run is the one line of the form
# "September 24 - November 7, 2026" (the year may be only on the end date).
_RANGE_LINE_RE = re.compile(
    r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\s*[-–—]\s*\S.*\d{4}\s*$')
_MAX_DESCRIPTION = 400


def scrape_transmission_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Transmission Gallery."""

    today = region_today(region)
    home = fetch_and_parse(BASE_URL + '/')
    if home is None:
        logging.warning("Transmission Gallery: could not fetch the home page; existing data kept.")
        return

    # The menu lists current shows first, then "Past Exhibitions Oakland";
    # only the links before that heading are read.
    links, seen = [], set()
    for a in home.find_all('a', href=True):
        label = a.get_text(' ', strip=True)
        if label.lower().startswith('past exhibitions'):
            break
        if ':' in label and a['href'].endswith('.html') and a['href'] not in seen:
            seen.add(a['href'])
            links.append((label, urljoin(BASE_URL, a['href'])))

    found = 0
    for name, url in links:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        lines = [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()]
        date_line = next((l for l in lines if _RANGE_LINE_RE.match(l)), None)
        if not date_line:
            logging.warning(f"Transmission Gallery: no date line for {name!r}")
            continue
        start_date, end_date = parse_date_text(date_line, today)
        if not (start_date and end_date):
            logging.warning(f"Transmission Gallery: no readable dates for {name!r}")
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue
        meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
        description = ' '.join(meta['content'].split())[:_MAX_DESCRIPTION] if meta and meta.get('content') else None

        event_details = {
            'name': name,
            'venue': 'Transmission Gallery',
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
        logging.warning("Transmission Gallery: no exhibitions found; existing data kept.")
