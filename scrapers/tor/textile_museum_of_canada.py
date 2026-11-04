from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

PROGRAMMING_URL = 'https://textilemuseum.ca/programming/'
# Each entry is a type line ("Exhibition", "Program", ...), the title, then the dates:
# "Oct 30, 2025, 12pm – Feb 1, 2027, 5pm"
_RANGE_RE = re.compile(
    r'^([A-Z][a-z]{2} \d{1,2}, \d{4}),? \d{1,2}(?::\d\d)?[ap]m [–-] ([A-Z][a-z]{2} \d{1,2}, \d{4}),? \d{1,2}(?::\d\d)?[ap]m$')


def scrape_textile_museum_of_canada(env='prod', region='tor'):
    """Scrape and process the exhibitions listed on the Textile Museum of Canada programming page."""
    today = region_today(region)
    soup = fetch_and_parse(PROGRAMMING_URL)
    if soup is None:
        logging.warning("Textile Museum of Canada: could not fetch the programming page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Textile Museum of Canada', soup, PROGRAMMING_URL)
    for i, line in enumerate(lines[:-2]):
        if line != 'Exhibition':
            continue
        m = _RANGE_RE.match(lines[i + 2])
        if not m:
            continue
        start_date, end_date = parse_date_text(f'{m.group(1)} - {m.group(2)}', today)
        listing.add(lines[i + 1], start_date, end_date, tag='museum')
    found = listing.publish()
    if not found:
        logging.warning("Textile Museum of Canada: no exhibitions found; existing data kept.")
