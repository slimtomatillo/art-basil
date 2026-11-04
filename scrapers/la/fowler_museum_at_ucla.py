from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://fowler.ucla.edu/exhibitions/'
VENUE = 'Fowler Museum at UCLA'
_FULL = r'[A-Z][a-z]+ \d{1,2}, \d{4}'
# "October 11, 2026 – May 16, 2027", or an end given only as a season ("August 9, 2026 – Summer 2027")
_RANGE_RE = re.compile(rf'^({_FULL}) [–-] ({_FULL})$')
_SEASON_RANGE_RE = re.compile(rf'^({_FULL}) [–-] (?:Spring|Summer|Fall|Autumn|Winter) \d{{4}}$')


def scrape_fowler_museum_at_ucla(env='prod', region='la'):
    """Scrape and process the exhibitions at the Fowler Museum at UCLA (admission is free)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Fowler Museum at UCLA: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines):
        if i < 1:
            continue
        if _RANGE_RE.match(line):
            start_date, end_date = parse_date_text(line, today)
        elif _SEASON_RANGE_RE.match(line):
            start_date, _ = parse_date_text(line.split(' – ')[0].split(' - ')[0], today)
            end_date = None
        else:
            continue
        # The title is the line above, or two above when a "by <artist>" byline sits between
        title = lines[i - 2] if lines[i - 1].lower().startswith('by ') and i >= 2 else lines[i - 1]
        listing.add(title, start_date, end_date, tag='museum', extra_tags=('free',))
    if not listing.publish():
        logging.warning("Fowler Museum at UCLA: no exhibitions found; existing data kept.")
