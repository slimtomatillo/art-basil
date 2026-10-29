from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://mannagallery.com'
# The "current" page lives at /current-1 (the /current path is a 404)
PAGES = (
    (BASE_URL + '/current-1', 'Manna Gallery presents'),
    (BASE_URL + '/upcoming', 'Upcoming show'),
)
_MONTH_START_RE = re.compile(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}')
_MAX_DESCRIPTION = 400


def scrape_manna_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows of Manna Gallery."""

    today = region_today(region)
    found = 0
    for url, marker in PAGES:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Manna Gallery: could not fetch {url}; existing data kept.")
            continue
        lines = [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()]
        # The show's title is the line after the page's marker line
        marker_idx = next((i for i, l in enumerate(lines) if l.lower() == marker.lower()), None)
        date_idx = next((i for i, l in enumerate(lines) if '-' in l and _MONTH_START_RE.match(l)), None)
        if marker_idx is None or marker_idx + 1 >= len(lines) or date_idx is None:
            logging.warning(f"Manna Gallery: could not read a show from {url}")
            continue
        name = lines[marker_idx + 1]
        start_date, end_date = parse_date_text(lines[date_idx], today)
        if not (start_date and end_date):
            logging.warning(f"Manna Gallery: no readable dates for {name!r}")
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        # Artist names / blurb: the lines between the title and the next section
        extra = [l for l in lines[marker_idx + 2:marker_idx + 12] if l != lines[date_idx] and not l.lower().startswith(('home', 'manna gallery', 'artist bios'))]
        description = ' '.join(extra)[:_MAX_DESCRIPTION] or None

        event_details = {
            'name': name,
            'venue': 'Manna Gallery',
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
        logging.warning("Manna Gallery: no exhibitions found; existing data kept.")
