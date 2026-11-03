from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

PAGE_URL = 'https://www.gallerytpw.ca/current-upcoming'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')
# Lines that open or close a block rather than belong to a title
_MARKERS = {'current', 'upcoming', 'learn more', 'in the td vitrine'}


def scrape_gallery_tpw(env='prod', region='tor'):
    """Scrape and process the current and upcoming programs at Gallery TPW."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Gallery TPW: could not fetch the current and upcoming page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    block = []
    for line in lines:
        if line.lower() in _MARKERS:
            block = []
            continue
        if not _RANGE_RE.match(line):
            block.append(line)
            continue
        # A block is the lines since the last marker: a title, or a series/biennial heading
        # followed by the exhibition title and then the artists' names.
        if block:
            name = block[0] if len(block) < 3 else f'{block[0]}: {block[1]}'
            start_date, end_date = parse_date_text(line, today)
            found += publish(env, region, 'Gallery TPW', name, start_date, end_date, PAGE_URL, tag='gallery')
        block = []
    if not found:
        logging.warning("Gallery TPW: no programs found; existing data kept.")
