"""Jack Shainman Gallery: the New York shows linked from its exhibitions page.

https://jackshainman.com/exhibitions lists the current shows as links to /exhibitions/<slug> with no dates; each show's
own page has the title, the run ("November 5 – December 19, 2026") and "Location 513 West 20th Street New York, NY".
The gallery also shows at The School in Kinderhook (upstate), which is left out: only a location in New York City is
kept, at 513 West 20th Street or 524 West 24th Street. The pictures are written without "https://" and are fixed here.
"""
import logging
import re

from processing import region_today
from scrapers.nyc import _pages
from scrapers.tor._common import publish
from utils import fetch_and_parse

LISTING = 'https://jackshainman.com/exhibitions'
VENUE = 'Jack Shainman Gallery'
SHOW_PATTERN = r'^/exhibitions/[a-z0-9_-]+/?$'
SUFFIX = ' « Exhibitions « Jack Shainman Gallery'
# (label, regex for the page's location text); the addresses are in docs/data/nyc_venues.json under the same labels
SPACES = [('513 West 20th Street', r'\b513 W(?:est|\.)? 20th'), ('524 West 24th Street', r'\b524 W(?:est|\.)? 24th')]


def _picture(url):
    """"https://jackshainman.com/exhibitions/jackshainman.com/uploads/..." is the page's og:image with its scheme missing."""
    if url and '/exhibitions/jackshainman.com/' in url:
        return 'https://jackshainman.com/' + url.split('/exhibitions/jackshainman.com/', 1)[1]
    return url


def scrape_jack_shainman_gallery(env='prod', region='nyc'):
    """Scrape and process Jack Shainman Gallery's New York exhibitions."""
    today = region_today(region)
    pages = {}

    def fetch(url):
        pages[url] = fetch_and_parse(url)
        return pages[url]

    listing = fetch(LISTING)
    if listing is None:
        logging.warning("Jack Shainman Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for url in _pages.show_links(listing, LISTING, SHOW_PATTERN):
        show = _pages.read_show(url, today, fetch=fetch, suffix=SUFFIX)
        if show is None:
            continue
        text = ' '.join(pages[url].get_text(' ').split())
        place = re.search(r'Location\s+(.{0,80})', text)
        place = place.group(1) if place else ''
        if 'New York, NY' not in place and not any(re.search(p, place) for _, p in SPACES):
            continue                                            # The School, Kinderhook
        spaces = [label for label, pattern in SPACES if re.search(pattern, place)] or None
        found += publish(env, region, VENUE, show['name'], show['start'], show['end'], url, tag='gallery', seen=seen,
                         image=_picture(show['image']), locations=spaces)
    if not found:
        logging.warning("Jack Shainman Gallery: no New York exhibition found; existing data kept.")
