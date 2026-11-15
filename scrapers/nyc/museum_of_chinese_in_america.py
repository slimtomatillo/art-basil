"""Museum of Chinese in America (MOCA), 215 Centre St: the exhibitions linked from its home page.

The site has no exhibitions listing, but its home page links the current shows (and its events) as /event/<slug>. A page
is an exhibition when it says "Category Exhibition", and its first run reads "October 22, 2026 – January 24, 2027" (the
core display, "With a Single Step", runs 2009 to 2028 and is left out as a standing display). Events (talks, tours)
are left out.
"""
import logging
import re

from processing import region_today
from scrapers.la._gallery import join_name
from scrapers.nyc import _pages
from scrapers.nyc._common import clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

HOME = 'https://www.mocanyc.org/'
VENUE = 'Museum of Chinese in America'
SUFFIX = ' – Museum of Chinese in America'
_RUN = re.compile(r'[A-Z][a-z]+ \d{1,2}, \d{4}\s*[–—-]\s*[A-Z][a-z]+ \d{1,2}, \d{4}')
_LONGEST_RUN = 900            # days; a longer one is the standing display


_SECTIONS = re.compile(r'^(?:contact|hours|follow|social media|moca newsletter|about|visit|related|share|tickets?)\b', re.IGNORECASE)


def _name(soup):
    """The show's name: the page's title is the generic "What's On", the show is the h2s after the site's h1 (the
    artist, then the title: "Hilda Shen" / "Their Landscapes"), up to the page's own sections."""
    names = []
    for heading in soup.find_all(['h1', 'h2']):
        text = clean(heading.get_text(' '))
        if text == VENUE:
            continue
        if not text or _SECTIONS.match(text) or len(text) > 80:
            break
        names.append(text)
    return join_name(names[:2])


def scrape_museum_of_chinese_in_america(env='prod', region='nyc'):
    """Scrape and process MOCA's current exhibitions."""
    today = region_today(region)
    home = fetch_and_parse(HOME)
    if home is None:
        logging.warning("Museum of Chinese in America: could not fetch the home page; existing data kept.")
        return
    found = 0
    seen = set()
    for url in _pages.show_links(home, HOME, r'^/event/'):
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        text = clean(_pages.fetch_copy(soup).get_text(' '))
        run = _RUN.search(text)
        if not run or not re.search(r'Category\s+Exhibition', text):
            continue
        start_date, end_date = parse_dates(run.group(0), today)
        name = _name(soup)
        if not (name and start_date and end_date) or (end_date - start_date).days > _LONGEST_RUN:
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, url, tag='museum', seen=seen,
                         image=_pages._picture(soup, url))
    if not found:
        logging.warning("Museum of Chinese in America: no current exhibition found; existing data kept.")
