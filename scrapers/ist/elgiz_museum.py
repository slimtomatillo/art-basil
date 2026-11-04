from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from processing import region_today
from urllib.parse import urljoin
import datetime as dt
import logging
import re

LISTING_URL = 'https://www.elgizmuseum.org/tr_TR/sergiler/temporary-exhibitions'
VENUE = 'Elgiz Museum of Contemporary Art'
# Each show reads "Title | Devamını Oku | Güncel | 28.08 - 28.11.2026" (Güncel = current, Geçmiş = past)
_NUMERIC_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})$')


def parse_numeric_range(text):
    """'28.08 - 28.11.2026' or '14.05.2025 - 31.05.2025' (day.month.year) -> (start, end), or (None, None)."""
    m = _NUMERIC_RE.match(text.strip())
    if not m:
        return None, None
    d1, m1, y1, d2, m2, y2 = m.groups()
    try:
        end = dt.date(int(y2), int(m2), int(d2))
        start = dt.date(int(y1 or y2), int(m1), int(d1))
        if not y1 and start > end:
            start = start.replace(year=start.year - 1)
        return start, end
    except ValueError:
        return None, None


def scrape_elgiz_museum(env='prod', region='ist'):
    """Scrape and process the temporary exhibitions at the Elgiz Museum of Contemporary Art."""
    region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Elgiz Museum: could not fetch the exhibitions page; existing data kept.")
        return
    links = {a.get_text(' ', strip=True): urljoin(LISTING_URL, a['href']) for a in soup.find_all('a', href=True)
             if '/temporary-exhibitions/' in a['href'] and a.get_text(' ', strip=True) != 'Devamını Oku'}
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, LISTING_URL)
    for i in range(2, len(lines) - 1):
        if lines[i - 1] != 'Devamını Oku' or lines[i] == 'Geçmiş':
            continue
        start, end = parse_numeric_range(lines[i + 1])
        title = lines[i - 2]
        if start or end:
            listing.add(title, start, end, link=links.get(title), tag='museum')
    if not listing.publish():
        logging.warning("Elgiz Museum: no current or upcoming exhibitions found; existing data kept.")
