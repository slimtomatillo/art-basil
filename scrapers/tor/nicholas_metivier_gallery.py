from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

PAGE_URL = 'https://metiviergallery.com/art-exhibitions/'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_nicholas_metivier_gallery(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at Nicholas Metivier Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Nicholas Metivier Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Nicholas Metivier Gallery', soup, PAGE_URL)
    # "Current" / "Upcoming" headings, then per show: artist / title / dates / "Read more"
    for i, line in enumerate(lines):
        if i < 2 or not _RANGE_RE.match(line):
            continue
        start_date, end_date = parse_date_text(line, today)
        listing.add(f'{lines[i - 2]}: {lines[i - 1]}', start_date, end_date, tag='gallery')
    found = listing.publish()
    if not found:
        logging.warning("Nicholas Metivier Gallery: no exhibitions found; existing data kept.")
