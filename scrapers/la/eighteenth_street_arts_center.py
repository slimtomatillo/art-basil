from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://18thstreet.org/exhibitions/'
VENUE = '18th Street Arts Center'
_DATE = r'[A-Z][a-z]+ \d{1,2}, \d{4}'
_DATE_RE = re.compile(rf'^({_DATE})(?: @ [\d:]+ [ap]m)?$')
_TIME_RE = re.compile(r'^[\d:]+ [ap]m$')


def scrape_eighteenth_street_arts_center(env='prod', region='la'):
    """Scrape and process the shows on view and upcoming at the 18th Street Arts Center."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("18th Street Arts Center: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    # "ON VIEW" and "UPCOMING EXHIBITIONS" come before the archive. Each entry is the title and then
    # its dates over three lines: "June 1, 2026" / "-" / "June 1, 2027". An event on one evening reads
    # "November 8, 2026 @ 2:00 pm" / "-" / "5:00 pm" and is stored as an event.
    end = next((i for i, l in enumerate(lines) if i > 3 and l.upper() in ('PAST EXHIBITIONS', 'PAST')), len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines[:end - 2]):
        m = _DATE_RE.match(line)
        if not (m and i and lines[i + 1] in ('-', '–')):
            continue
        closing = lines[i + 2]
        if _TIME_RE.match(closing):
            start_date, _ = parse_date_text(m.group(1), today)
            listing.add(lines[i - 1], start_date, start_date, tag='gallery', kind='event')
        elif _DATE_RE.match(closing):
            start_date, end_date = parse_date_text(f'{m.group(1)} - {_DATE_RE.match(closing).group(1)}', today)
            listing.add(lines[i - 1], start_date, end_date, tag='gallery')
    if not listing.publish():
        logging.warning("18th Street Arts Center: no shows found; existing data kept.")
