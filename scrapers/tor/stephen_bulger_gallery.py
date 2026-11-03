from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

HOME_URL = 'https://www.bulgergallery.com/'
_DATES_RE = re.compile(r'^Exhibition Dates:\s*(.+)$')


def scrape_stephen_bulger_gallery(env='prod', region='tor'):
    """Scrape and process the exhibitions shown on the Stephen Bulger Gallery home page."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Stephen Bulger Gallery: could not fetch the home page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    seen = set()
    # Each slide: ARTIST / title / "Opening Reception: ..." / "Exhibition Dates: October 31 – December 19, 2026"
    for i, line in enumerate(lines):
        m = _DATES_RE.match(line)
        if not m or i < 3:
            continue
        artist, title = lines[i - 3], lines[i - 2]
        start_date, end_date = parse_date_text(m.group(1), today)
        found += publish(env, region, 'Stephen Bulger Gallery', f'{artist.title()}: {title}', start_date, end_date,
                         HOME_URL, tag='gallery', seen=seen)
    if not found:
        logging.warning("Stephen Bulger Gallery: no exhibitions found; existing data kept.")
