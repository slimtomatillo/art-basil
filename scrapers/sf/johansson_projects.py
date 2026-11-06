"""Johansson Projects (2300 Telegraph Ave, Oakland), a contemporary gallery on the ArtCloud platform.

The exhibitions page is built in the browser from a JSON endpoint, /api/shows, which the page's own
script calls with the site's id ("sub") and a limit. Each show has a title ("Gregory Rick // Night
Watch"), a run as text ("September 30 - November 14, 2026"), an opening reception, an id slug for its
page (/show/<showId>) and a picture, which ArtCloud's CDN serves by id at any size. The newest shows
come first, so the first 100 cover everything current and upcoming.
"""
import logging
import re

import requests

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish

BASE_URL = 'https://johanssonprojects.com'
PAGE_URL = BASE_URL + '/exhibitions'
API_URL = BASE_URL + '/api/shows'
VENUE = 'Johansson Projects'
# The id the site's own page sends; read from the page each run, with this as the fallback
FALLBACK_SUB = '341e42e8-558f-4c45-a124-97cf867f015c'
_SUB_RE = re.compile(r'"subdomain":"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"')
_PICTURE = 'https://cdn.artcld.com/img/w_640,h_640,c_fit/{id}.{ext}'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
# The list mixes the gallery's own shows with its art-fair booths, which are elsewhere and not at the gallery
_FAIR_RE = re.compile(r'\bart fair\b|\bfair\b|\buntitled miami\b|\bfelix\b|^fog\b|\bfrieze\b|\bexpo\b|\bnada\b|\bart basel\b', re.I)


def _site_id():
    try:
        match = _SUB_RE.search(requests.get(PAGE_URL, headers=HEADERS, timeout=30).text)
    except requests.RequestException:
        match = None
    return match.group(1) if match else FALLBACK_SUB


def scrape_johansson_projects(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions at Johansson Projects."""
    today = region_today(region)
    try:
        response = requests.get(API_URL, params={'limit': 100, 'offset': 0, 'sub': _site_id()},
                                headers={**HEADERS, 'Accept': 'application/json'}, timeout=30)
        response.raise_for_status()
        shows = response.json().get('shows') or []
    except (requests.RequestException, ValueError, AttributeError) as e:
        logging.warning(f"Johansson Projects: could not fetch the shows feed ({e}); existing data kept.")
        return
    stored = 0
    seen = set()
    for show in shows:
        raw_title = ' '.join((show.get('title') or '').split())
        if not raw_title or _FAIR_RE.search(raw_title):
            continue
        start_date, end_date = parse_date_text(show.get('date') or '', today)
        picture = show.get('image') or {}
        stored += publish(env, region, VENUE, raw_title.replace(' // ', ': '), start_date, end_date,
                          f"{BASE_URL}/show/{show['showId']}" if show.get('showId') else PAGE_URL,
                          tag='gallery', seen=seen,
                          image=_PICTURE.format(id=picture['id'], ext=picture.get('extension') or 'jpg')
                          if picture.get('id') else None)
    if not stored:
        logging.warning("Johansson Projects: no current or upcoming shows found; existing data kept.")
