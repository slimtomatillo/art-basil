"""Queens Museum, Flushing Meadows Corona Park: the exhibitions at queensmuseum.org/exhibitions/current.

The listing links to each show's page (/exhibition/<slug>/). A page's title is only the show's title ("Queens Museum |
Demonstrate") and it has no share picture; the artist, the title and the run are lines of its text: "Sonia Boyce",
"Demonstrate", "06.27.26 – 02.07.27" (month.day.year). A group show has no artist line. Shows with "Ongoing" for an end
date are the museum's long-term commissions at LaGuardia Airport, not shows here, and are left out (WEBSITE-121).
"""
import logging
import re

from processing import region_today
from scrapers.nyc import _pages
from scrapers.nyc._common import clean, numeric_run
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Queens Museum'
LISTINGS = ['https://queensmuseum.org/exhibitions/current']
SHOW_PATTERN = r'/exhibition/[a-z0-9-]+'
_RUN = re.compile(r'^\d{1,2}\.\d{1,2}\.\d{2,4}\s*[–—-]\s*\d{1,2}\.\d{1,2}\.\d{2,4}$')


def read_show(soup, today):
    """{name, start, end, description} from a show's page, or None when it has no dated run."""
    page = _pages.fetch_copy(soup)
    lines = [clean(line) for line in page.get_text('\n').split('\n') if clean(line)]
    at = next((i for i, line in enumerate(lines[:80]) if _RUN.match(line)), None)
    if at is None or at < 2:
        return None
    start, end = numeric_run(lines[at])
    if not (start and end):
        return None
    title = lines[at - 1]
    artist = lines[at - 2]
    # "Exhibitions - Demonstrate" is the breadcrumb line above the title (and above the artist, for a solo show)
    name = title if artist.startswith('Exhibitions - ') else f'{artist}: {title}'
    return {'name': name, 'start': start, 'end': end, 'description': _pages._description(soup, name)}


def scrape_queens_museum(env='prod', region='nyc'):
    """Scrape and process the Queens Museum's current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    links = []
    for listing in LISTINGS:
        soup = fetch_and_parse(listing)
        if soup is None:
            logging.warning(f"{VENUE}: could not fetch {listing}; existing data kept.")
            continue
        links += [url for url in _pages.show_links(soup, listing, SHOW_PATTERN) if url not in links]
    for url in links:
        page = fetch_and_parse(url)
        show = read_show(page, today) if page is not None else None
        if show:
            found += publish(env, region, VENUE, show['name'], show['start'], show['end'], url, tag='museum',
                             description=show['description'], seen=seen)
    if not found:
        logging.warning(f"{VENUE}: no current or upcoming exhibition found; existing data kept.")
    return found
