from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

PAGE_URL = 'https://www.paulpetro.com/ppca/current'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_paul_petro_contemporary_art(env='prod', region='tor'):
    """Scrape and process the current exhibitions at Paul Petro Contemporary Art."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Paul Petro: could not fetch the current page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    # Each show is: title / artist / subtitle / dates / opening reception.
    # "Current Regional Programming" (art-fair booths) sits in the same list and is skipped.
    for i, line in enumerate(lines):
        if i < 3 or not _RANGE_RE.match(line) or 'regional programming' in lines[i - 1].lower():
            continue
        title, artist, subtitle = lines[i - 3:i]
        start_date, end_date = parse_date_text(line, today)
        found += publish(env, region, 'Paul Petro Contemporary Art', f'{title}: {artist} - {subtitle}',
                         start_date, end_date, PAGE_URL, tag='gallery')
    if not found:
        logging.warning("Paul Petro: no exhibitions found; existing data kept.")
