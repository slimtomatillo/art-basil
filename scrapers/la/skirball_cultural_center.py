from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://www.skirball.org/museum/exhibitions'
VENUE = 'Skirball Cultural Center'
# Each show under "On View Now" is its title followed by "On view through February 28, 2027".
# Permanent displays say "Ongoing" and are skipped.
_THROUGH_RE = re.compile(r'^On view (through .+)$', re.I)


def scrape_skirball_cultural_center(env='prod', region='la'):
    """Scrape and process the exhibitions on view at the Skirball Cultural Center."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Skirball Cultural Center: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines):
        m = _THROUGH_RE.match(line)
        if m and i:
            start_date, end_date = parse_date_text(m.group(1), today)
            listing.add(lines[i - 1], start_date, end_date, tag='museum')
    if not listing.publish():
        logging.warning("Skirball Cultural Center: no exhibitions found; existing data kept.")
