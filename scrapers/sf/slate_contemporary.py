from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

import requests

# The exhibitions page fills itself from the site's own JSON endpoint (the
# artcld.com platform); "sub" is the site's account name. It lists gallery shows,
# the off-site shows SLATE curates in other buildings, and the archive back to 2024.
API_URL = 'https://slatecontemporary.com/api/shows'
API_PARAMS = {'sub': 'slateart', 'limit': 100}
SHOW_URL = 'https://slatecontemporary.com/show/'

# Off-site shows hang in other buildings and carry the building in the title
# ("225 WEST SANTA CLARA: ...", "POST MONTGOMERY CENTER: ...", "... at the North
# Block Hotel"); they are not at the College Ave gallery, so they are skipped.
_OFFSITE_RE = re.compile(
    r'^\d|post montgomery|north block hotel|nordstrom|design center|levi.?s plaza|minnesota street',
    re.I)


def scrape_slate_contemporary(env='prod', region='sf'):
    """Scrape and process the current and upcoming gallery shows of SLATE contemporary."""

    today = region_today(region)
    try:
        response = requests.get(API_URL, params=API_PARAMS, headers={'User-Agent': 'Your Bot 0.1'}, timeout=30)
        response.raise_for_status()
        shows = response.json().get('shows', [])
    except (requests.RequestException, ValueError) as e:
        logging.warning(f"SLATE contemporary: could not fetch the shows list ({e}); existing data kept.")
        return
    if not shows:
        logging.warning("SLATE contemporary: the shows list was empty; existing data kept.")
        return

    for show in shows:
        name = (show.get('title') or '').strip()
        if not name or _OFFSITE_RE.search(name):
            continue
        start_date, end_date = parse_date_text(show.get('date') or '', today)
        if not (start_date and end_date):
            logging.warning(f"SLATE contemporary: no readable dates for {name!r}")
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue

        event_details = {
            'name': name,
            'venue': 'SLATE Contemporary',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': SHOW_URL + show['showId'], 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
