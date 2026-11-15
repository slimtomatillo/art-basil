"""New Museum, 235 Bowery: the exhibitions in its listing page's data.

https://www.newmuseum.org/exhibitions/ is a Next.js page whose cards are built in the browser, but the HTML carries
the shows in its __NEXT_DATA__ script: pageProps.__TEMPLATE_QUERY_DATA__.page.blocks[...].exhibitions is a list per
block (Current, Upcoming...) of objects with a title, startDate, endDate, a link to the show's page and a featured
image. A display with no end date (the "Ongoing" Plaza, Facade and Atrium Stair commissions) is left out.
"""
import datetime as dt
import json
import logging

from processing import region_today
from scrapers.nyc._common import clean
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.newmuseum.org/exhibitions/'
VENUE = 'New Museum'
_LONGEST_RUN = 600           # days; the long-term commissions are entered with an end date about two years out


def _day(text):
    try:
        return dt.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _exhibitions(soup):
    """Every exhibition object in the page's data, or []."""
    script = soup.find('script', id='__NEXT_DATA__')
    try:
        blocks = json.loads(script.string or script.get_text())['props']['pageProps']['__TEMPLATE_QUERY_DATA__']['page']['blocks']
    except (AttributeError, KeyError, TypeError, ValueError):
        return []
    found = []
    for block in blocks or []:
        if isinstance(block, dict):
            found += [e for e in block.get('exhibitions') or [] if isinstance(e, dict)]
    return found


def _picture(item):
    try:
        return item['featuredImage']['node']['sourceUrl'] or None
    except (KeyError, TypeError):
        return None


def scrape_new_museum(env='prod', region='nyc'):
    """Scrape and process the New Museum's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("New Museum: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for item in _exhibitions(soup):
        name = clean(item.get('title'))
        start_date, end_date = _day(item.get('startDate')), _day(item.get('endDate'))
        if not (name and item.get('link') and end_date):
            continue                                            # no end date: an ongoing commission
        if start_date and (end_date - start_date).days > _LONGEST_RUN:
            continue                                            # a placeholder end two years out: the "Ongoing" commissions
        found += publish(env, region, VENUE, name, start_date, end_date, item['link'], tag='museum', seen=seen,
                         image=_picture(item))
    if not found:
        logging.warning("New Museum: no current or upcoming exhibition found; existing data kept.")
