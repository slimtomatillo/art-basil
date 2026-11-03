from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

PAGE_URL = 'https://www.ocadu.ca/galleries/onsite-gallery'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}, \d{4} [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_onsite_gallery(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at OCAD University's Onsite Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Onsite Gallery: could not fetch the gallery page; existing data kept.")
        return
    lines = page_lines(soup)
    # Only the exhibition sections count; the events list below it has its own dates
    start = next((i for i, l in enumerate(lines) if l.lower() == 'current exhibitions'), None)
    if start is None:
        logging.warning("Onsite Gallery: no 'Current exhibitions' section found; existing data kept.")
        return
    end = next((i for i, l in enumerate(lines) if i > start and l.lower().startswith('upcoming programming')), len(lines))
    found = 0
    seen = set()
    # Each show: title / "September 2, 2026 - January 30, 2027" / location / "Exhibition"
    for i in range(start + 1, end):
        if _RANGE_RE.match(lines[i]):
            start_date, end_date = parse_date_text(lines[i], today)
            found += publish(env, region, 'Onsite Gallery', lines[i - 1], start_date, end_date, PAGE_URL,
                             tag='gallery', seen=seen)
    if not found:
        logging.warning("Onsite Gallery: no exhibitions found; existing data kept.")
