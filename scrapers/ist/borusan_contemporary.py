from utils import fetch_and_parse
from scrapers.sf._artlogic import parse_day_first_range
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

# Use the www address: the bare borusancontemporary.com has a certificate for another name
URLS = ['https://www.borusancontemporary.com/en/current-exhibitions_12', 'https://www.borusancontemporary.com/en/upcoming-exhibitions_13']
VENUE = 'Borusan Contemporary'
# "Haunted | 19 September 2026 - 15 August 2027 | COLLECTION EXHIBITION | CURATOR: DR. KUMRU EREN"
_RANGE_RE = re.compile(r'^\d{1,2} [A-Za-z]+ \d{4}\s*[-–]\s*\d{1,2} [A-Za-z]+ \d{4}$')


def scrape_borusan_contemporary(env='prod', region='ist'):
    """Scrape and process the current and upcoming exhibitions at Borusan Contemporary."""
    region_today(region)
    seen = set()
    fetched = stored = 0
    for url in URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        fetched += 1
        lines = page_lines(soup)
        listing = Listing(env, region, VENUE, soup, url)
        for i in range(1, len(lines)):
            if _RANGE_RE.match(lines[i]):
                start, end = parse_day_first_range(lines[i])
                if start and end:
                    listing.add(lines[i - 1], start, end, tag='museum', seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("Borusan Contemporary: could not fetch the exhibition pages; existing data kept.")
    elif not stored:
        logging.warning("Borusan Contemporary: no exhibitions found; existing data kept.")
