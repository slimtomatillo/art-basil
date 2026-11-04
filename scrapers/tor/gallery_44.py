from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

PAGE_URL = 'https://www.gallery44.org/exhibitions-and-public-programs'
_MONTH_DAY_RE = re.compile(r'^[A-Z][a-z]{2} \d{1,2}$')


def scrape_gallery_44(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at Gallery 44."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Gallery 44: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Gallery 44', soup, PAGE_URL)
    # Dates are split over three lines ("Sep 18" / "–" / "Nov 7"), then the space, then the title
    for i, line in enumerate(lines[:-4]):
        if not (_MONTH_DAY_RE.match(line) and lines[i + 1] in ('–', '-') and _MONTH_DAY_RE.match(lines[i + 2])):
            continue
        start_date, end_date = parse_date_text(f'{line} - {lines[i + 2]}', today)
        listing.add(lines[i + 4], start_date, end_date, tag='gallery')
    found = listing.publish()
    if not found:
        logging.warning("Gallery 44: no exhibitions found; existing data kept.")
