"""The Ronna and Eric Hoffman Gallery of Contemporary Art, Lewis & Clark College (615 S Palatine Hill Rd): its home page
shows the "Current Exhibition" as a news item, and the item's own page says the run in a sentence ("The exhibition opens on
Sunday, August 30, 2026 and continues through to December 10th."), so the dates are read from that sentence.
"""
import datetime as dt
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import clean
from scrapers.nyc._pages import _description, _meta, _picture
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Hoffman Gallery'
PAGE_URL = 'https://www.lclark.edu/hoffman_gallery/'
_MONTHS = {m.lower(): i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'], 1)}
_DAY = r'(?:(?i:mon|tues|wednes|thurs|fri|satur|sun)day,?\s+)?'
_DATE = r'([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*(\d{4}))?'
_RUN = re.compile(r'(?i:opens?|open from|runs?|on view)\s+(?:on\s+)?' + _DAY + _DATE +
                  r'\s*(?:and\s+continues\s+(?:through|until)(?:\s+to)?|through|until|to|[-–—])\s*' + _DAY + _DATE)


def parse_sentence(text, today):
    """(start, end) from a sentence like "opens on Sunday, August 30, 2026 and continues through to December 10th"."""
    match = _RUN.search(clean(text))
    if not match:
        return None, None
    m1, d1, y1, m2, d2, y2 = match.groups()
    if m1.lower() not in _MONTHS or m2.lower() not in _MONTHS:
        return None, None
    year1 = int(y1) if y1 else (int(y2) if y2 else today.year)
    try:
        start = dt.date(year1, _MONTHS[m1.lower()], int(d1))
        end = dt.date(int(y2) if y2 else year1, _MONTHS[m2.lower()], int(d2))
    except ValueError:
        return None, None
    if end < start:                                    # "opens December 5 and continues through January 20"
        end = end.replace(year=end.year + 1)
    return start, end


def read_current(soup, page_url):
    """The link to the current exhibition's page from the home page, or None."""
    heading = soup.find('h3', string=re.compile('Current Exhibition', re.IGNORECASE))
    link = heading.parent.select_one('a[href]') if heading and heading.parent else None
    return urljoin(page_url, link['href']) if link else None


def scrape_hoffman_gallery(env='prod', region='pdx'):
    """Scrape and process the Hoffman Gallery's current exhibition."""
    today = region_today(region)
    home = fetch_and_parse(PAGE_URL)
    if home is None:
        logging.warning("Hoffman Gallery: could not fetch the gallery page; existing data kept.")
        return
    url = read_current(home, PAGE_URL)
    page = fetch_and_parse(url) if url else None
    found = 0
    if page is not None:
        name = _meta(page, property='og:title') or clean(page.find('h1').get_text(' ') if page.find('h1') else '')
        start, end = parse_sentence(page.get_text(' '), today)
        if name and (start or end):
            found = publish(env, region, VENUE, name, start, end, url, tag='gallery', description=_description(page, name),
                            image=_picture(page, url))
    if not found:
        logging.warning("Hoffman Gallery: no current or upcoming exhibition found; existing data kept.")
