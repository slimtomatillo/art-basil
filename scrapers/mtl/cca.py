from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from processing import region_today
import datetime as dt
import logging
import re

EXHIBITIONS_URL = 'https://www.cca.qc.ca/en/about-exhibitions'
VENUE = 'Canadian Centre for Architecture'
# "On view" / "Upcoming" lists, each show as a title line then a sentence:
#   "is on display in our Main Galleries until 10 January 2027."  /  "opens in our Main Galleries on 18 March 2027."
_DATE_RE = re.compile(r'\b(\d{1,2} [A-Z][a-z]+ \d{4})')


def scrape_cca(env='prod', region='mtl'):
    """Scrape and process the shows on view and upcoming at the Canadian Centre for Architecture."""
    region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("CCA: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    if 'On view' not in lines:
        logging.warning("CCA: no 'On view' list on the exhibitions page; existing data kept.")
        return
    begin = lines.index('On view')
    stored = 0
    for i in range(begin + 1, len(lines)):
        if lines[i].startswith('We see each exhibition'):
            break
        m = _DATE_RE.search(lines[i])
        if not (m and i > begin + 1 and lines[i].startswith(('is ', 'will ', 'opens '))):
            continue
        start, end = dt.datetime.strptime(m.group(1), '%d %B %Y').date(), None
        # "until 10 January 2027" is an end date; "on 5 November 2026" / "opens ... on 18 March 2027" a start date
        if re.search(r'\buntil\b', lines[i]):
            start, end = None, start
        stored += publish(env, region, VENUE, lines[i - 1], start, end, EXHIBITIONS_URL, tag='museum')
    if not stored:
        logging.warning("CCA: no exhibitions found; existing data kept.")
