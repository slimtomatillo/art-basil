from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import calendar
import datetime as dt
import logging
import re

EXHIBITIONS_URL = 'https://wendemuseum.org/exhibitions/'
VENUE = 'Wende Museum'
# Runs are given by month: "Nov 2026-Jan 2027" under the title, in the "CURRENT" and "Upcoming" lists
_RANGE_RE = re.compile(r'^([A-Z][a-z]{2}) (\d{4})\s*[-–]\s*([A-Z][a-z]{2}) (\d{4})$')
_MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def _month_range(text):
    """'Nov 2026-Jan 2027' -> (Nov 1, 2026, Jan 31, 2027), or (None, None)."""
    m = _RANGE_RE.match(text)
    if not (m and m.group(1) in _MONTHS and m.group(3) in _MONTHS):
        return None, None
    y2, m2 = int(m.group(4)), _MONTHS[m.group(3)]
    return dt.date(int(m.group(2)), _MONTHS[m.group(1)], 1), dt.date(y2, m2, calendar.monthrange(y2, m2)[1])


def scrape_wende_museum(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at the Wende Museum (a free museum)."""
    region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Wende Museum: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines):
        start_date, end_date = _month_range(line)
        if not (start_date and i >= 2):
            continue
        # A work's name and a long all-caps notice can sit above the date; the title is then the line above that
        title = lines[i - 2] if lines[i - 1].isupper() else lines[i - 1]
        # One entry puts a notice after the name ("Bumdog Torres | THIS STRUCTURE WILL BE REMOVED...")
        listing.add(title.split(' | ')[0], start_date, end_date, tag='museum', extra_tags=('free',))
    if not listing.publish():
        logging.warning("Wende Museum: no exhibitions found; existing data kept.")
