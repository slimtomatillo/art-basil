from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://www.gardinermuseum.on.ca/whats-on/exhibitions/'
# "Sep 18 2026 – Nov 15 2026" on the line under each exhibition title
_RANGE_RE = re.compile(r'^[A-Z][a-z]{2} \d{1,2} \d{4} [–-] [A-Z][a-z]{2} \d{1,2} \d{4}$')


def scrape_gardiner_museum(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions of the Gardiner Museum."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Gardiner Museum: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Gardiner Museum', soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines):
        if i and _RANGE_RE.match(line):
            start_date, end_date = parse_date_text(line, today)
            listing.add(lines[i - 1], start_date, end_date, tag='museum')
    found = listing.publish()
    if not found:
        logging.warning("Gardiner Museum: no exhibitions found; existing data kept.")
