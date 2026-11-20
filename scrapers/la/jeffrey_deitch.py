"""Jeffrey Deitch, Los Angeles (925 N Orange Dr and 7000 Santa Monica Blvd).

The site shows nothing without JavaScript, but the script loads each section from a plain JSON
address, /lazystate/<section>. /lazystate/los-angeles holds every Los Angeles exhibition ever shown
(newest first) with its title, artists, opening and closing dates (ISO, "2026-10-30") and text, so it is
read directly: no browser rendering and no proxy needed. The answer is large (about 650 KB).
"""
import datetime as dt
import logging
import re

from bs4 import BeautifulSoup

from scrapers.tor._common import publish
from utils import fetch_json

BASE_URL = 'https://www.deitch.com'
STATE_URL = BASE_URL + '/lazystate/los-angeles'
VENUE = 'Jeffrey Deitch Los Angeles'
_MAX_DESCRIPTION = 400
# Each show says where it is ("925 N. Orange Drive, Los Angeles", "7000 Santa Monica Blvd., Los Angeles", or both with "and" or
# "&"); the labels are those of the venue's addresses in la_venues.json (WEBSITE-122). A place that is neither (an older show
# at 1114 Horn Avenue) gives None, which stores the show for the venue as a whole.
SPACES = (('Orange Drive', r'Orange Dr'), ('Santa Monica Boulevard', r'Santa Monica'))


def spaces(location):
    """The labels of the gallery's spaces a show's location names, or None."""
    return [label for label, pattern in SPACES if re.search(pattern, location or '', re.IGNORECASE)] or None


def _date(text):
    try:
        return dt.date.fromisoformat(text) if text else None
    except ValueError:
        return None


def _description(html):
    """The exhibition text without its "Opening reception" line, cut at a word."""
    paragraphs = [' '.join(p.get_text().split()) for p in BeautifulSoup(html or '', 'html.parser').find_all('p')]
    text = ' '.join(p for p in paragraphs if p and not p.lower().startswith('opening reception'))
    if len(text) > _MAX_DESCRIPTION:
        text = text[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
    return text or None


def _image(show):
    for info in (show.get('files') or {}).values():
        if info.get('type') == 'image':
            sizes = info.get('sizes') or {}
            path = sizes.get('1000') or sizes.get('500') or info.get('url')
            return BASE_URL + path if path else None
    return None


def scrape_jeffrey_deitch(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions of Jeffrey Deitch's Los Angeles galleries."""
    state = fetch_json(STATE_URL)
    if not isinstance(state, dict):
        logging.warning("Jeffrey Deitch: could not read the Los Angeles listing; existing data kept.")
        return
    found = 0
    seen = set()
    for path, show in state.items():
        if not isinstance(show, dict) or show.get('template') != 'exhibition':
            continue
        title = ' '.join((show.get('title') or '').split())
        start_date, end_date = _date(show.get('openingdate')), _date(show.get('closingdate'))
        found += publish(env, region, VENUE, title, start_date, end_date, BASE_URL + path, tag='gallery',
                         description=_description(show.get('text')), seen=seen, image=_image(show),
                         locations=spaces(show.get('location')))
    if not found:
        logging.warning("Jeffrey Deitch: no current or upcoming exhibitions on the Los Angeles listing; existing data kept.")
