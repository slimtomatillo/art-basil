from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from date_parsing import parse_date_text
from processing import region_today
import logging
import re

LISTING_URL = 'https://skol.ca/expositions/'
VENUE = 'SKOL'
# Each show is a title line, then a line such as "Exposition individuelle ... Du 10 septembre au 28 novembre 2026 ..."
_DATES_RE = re.compile(r'\b[Dd]u (\d{1,2}(?:er)? \w+ au \d{1,2}(?:er)? \w+ \d{4})')
_SINGLE_MONTH_RE = re.compile(r'\b[Dd]u (\d{1,2}(?:er)? au \d{1,2}(?:er)? \w+ \d{4})')


def scrape_skol(env='prod', region='mtl'):
    """Scrape and process the exhibitions at SKOL, centre des arts actuels."""
    today = region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("SKOL: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    footer = max((i for i, l in enumerate(lines) if l.startswith('©')), default=-1)
    listing = Listing(env, region, VENUE, soup, LISTING_URL)
    for i in range(footer + 2, len(lines)):
        m = _DATES_RE.search(lines[i]) or _SINGLE_MONTH_RE.search(lines[i])
        if not m:
            continue
        start, end = parse_date_text(m.group(1), today)
        if start or end:
            listing.add(lines[i - 1], start, end, tag='gallery')
    if not listing.publish():
        logging.warning("SKOL: no exhibitions found; existing data kept.")
