from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

PAGE_URL = 'https://coopercolegallery.com/exhibitions/'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [–-] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_cooper_cole(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at Cooper Cole."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Cooper Cole: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    seen = set()
    # Each show appears as artist / title / dates (and again as a caption that starts with
    # "COOPER COLE, Toronto, Canada", which is skipped); the archive back to 2011 follows
    for i, line in enumerate(lines):
        if i < 2 or not _RANGE_RE.match(line) or lines[i - 2].startswith('COOPER COLE'):
            continue
        start_date, end_date = parse_date_text(line, today)
        found += publish(env, region, 'Cooper Cole', f'{lines[i - 2]}: {lines[i - 1]}', start_date, end_date,
                         PAGE_URL, tag='gallery', seen=seen)
    if not found:
        logging.warning("Cooper Cole: no current or upcoming exhibitions on the page (between shows?); existing data kept.")
