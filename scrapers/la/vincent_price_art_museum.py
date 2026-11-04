from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://vpam.org/exhibitions/'
VENUE = 'Vincent Price Art Museum'
# "SEPTEMBER 26, 2026 – MAY 22, 2027" under each title; the archive follows "PAST EXHIBITIONS"
_RANGE_RE = re.compile(r'^[A-Za-z]+ \d{1,2}, \d{4} [–-] [A-Za-z]+ \d{1,2}, \d{4}$')


def scrape_vincent_price_art_museum(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at the Vincent Price Art Museum (free)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Vincent Price Art Museum: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    # "Past Exhibitions" is also a menu link near the top, so the archive starts at the heading after "CURRENT"
    start = next((i for i, l in enumerate(lines) if l.upper() == 'CURRENT'), 0)
    end = next((i for i, l in enumerate(lines) if i > start and l.upper() == 'PAST EXHIBITIONS'), len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines[:end]):
        if i > start and _RANGE_RE.match(line):
            start_date, end_date = parse_date_text(line, today)
            listing.add(lines[i - 1], start_date, end_date, tag='museum', extra_tags=('free',))
    if not listing.publish():
        logging.warning("Vincent Price Art Museum: no exhibitions found; existing data kept.")
