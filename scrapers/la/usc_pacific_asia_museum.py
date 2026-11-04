from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re

EXHIBITIONS_URL = 'https://pacificasiamuseum.usc.edu/whats-on-view/'
VENUE = 'USC Pacific Asia Museum'
# "Oct. 17, 2026 – Jan. 10, 2027" on the line under each title, in the "Current Exhibitions" and
# "Upcoming Exhibitions" sections; the virtual and past exhibitions follow.
_RANGE_RE = re.compile(r'^[A-Z][a-z]+\.? \d{1,2}, \d{4} [–-] [A-Z][a-z]+\.? \d{1,2}, \d{4}$')


def scrape_usc_pacific_asia_museum(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at the USC Pacific Asia Museum."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("USC Pacific Asia Museum: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    # "Past Exhibitions" is also a menu link above the list, so the archive is what follows the first date
    first = next((i for i, l in enumerate(lines) if _RANGE_RE.match(l)), None)
    if first is None:
        logging.warning("USC Pacific Asia Museum: no exhibition dates found; existing data kept.")
        return
    end = next((i for i, l in enumerate(lines) if i > first and l in ('Past Exhibitions', 'Virtual Exhibitions')), len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i in range(first, end):
        if _RANGE_RE.match(lines[i]):
            start_date, end_date = parse_date_text(lines[i], today)
            listing.add(lines[i - 1], start_date, end_date, tag='museum')
    if not listing.publish():
        logging.warning("USC Pacific Asia Museum: no exhibitions found; existing data kept.")
