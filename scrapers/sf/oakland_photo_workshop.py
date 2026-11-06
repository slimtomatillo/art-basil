"""Oakland Photo Workshop (312 8th St, Oakland): the gallery of the East Bay Photo Collective.

The collective's exhibitions calendar (ebpco.org/exhibitions-calendar) is a Squarespace events
collection, which serves its data as JSON when asked with ?format=json: "upcoming" holds the
shows on now and still to come, "past" the rest. Dates are epoch milliseconds in UTC, so they are
converted to Pacific time (a 6 PM opening on Oct 2 is Oct 3 in UTC).
"""
import datetime as dt
import logging
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from scrapers.tor._common import publish

BASE_URL = 'https://www.ebpco.org'
FEED_URL = BASE_URL + '/exhibitions-calendar?format=json'
VENUE = 'Oakland Photo Workshop'
PACIFIC = ZoneInfo('America/Los_Angeles')
_MAX_DESCRIPTION = 400
# Some calendar entries are held elsewhere (the collective's early shows at Oakland School for the Arts
# and on Mandela Parkway); a show with a different street address is not at this gallery
_HOME_ADDRESS = re.compile(r'312\s+8th', re.I)
_NOT_A_SHOW = {'notice'}


def _day(epoch_ms):
    """The local (Pacific) date of an epoch-milliseconds timestamp, or None."""
    try:
        return dt.datetime.fromtimestamp(int(epoch_ms) / 1000, PACIFIC).date()
    except (TypeError, ValueError, OSError):
        return None


def _is_here(item):
    address = ((item.get('location') or {}).get('addressLine1') or '').strip()
    return not address or bool(_HOME_ADDRESS.search(address))


def scrape_oakland_photo_workshop(env='prod', region='sf'):
    """Scrape and process the current and upcoming shows at the Oakland Photo Workshop."""
    try:
        response = requests.get(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        items = response.json().get('upcoming') or []
    except (requests.RequestException, ValueError, AttributeError) as e:
        logging.warning(f"Oakland Photo Workshop: could not fetch the exhibitions feed ({e}); existing data kept.")
        return
    stored = 0
    seen = set()
    for item in items:
        title = ' '.join((item.get('title') or '').split())
        if not title or title.lower() in _NOT_A_SHOW or not _is_here(item):
            continue
        start, end = _day(item.get('startDate')), _day(item.get('endDate'))
        excerpt = BeautifulSoup(item.get('excerpt') or '', 'html.parser').get_text(' ', strip=True)
        excerpt = re.sub(r'\s+([?.,!;:])', r'\1', excerpt)          # no stray space where a tag ended before punctuation
        description = excerpt[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(excerpt) > _MAX_DESCRIPTION else excerpt
        picture = item.get('assetUrl')
        stored += publish(env, region, VENUE, title, start, end,
                          urljoin(BASE_URL, item.get('fullUrl') or '/exhibitions-calendar'), tag='gallery',
                          description=description or None, seen=seen,
                          # Squarespace resizes its pictures on request; the originals are several MB
                          image=f'{picture}?format=750w' if picture else None)
    if not stored:
        logging.warning("Oakland Photo Workshop: no current or upcoming shows found; existing data kept.")
