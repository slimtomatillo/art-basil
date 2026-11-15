"""Sikkema Malloy Jenkins, 530 W 22nd St: the shows under "Current exhibitions" on its page.

https://www.sikkemajenkinsco.com/current-exhibitions is a Squarespace page. Each current show is an h2 holding a link
whose text is the artist, the title and the run on three lines ("HEIDI LAU / OUROBOROS / 10.30-12.19.26": month.day to
month.day.year). The recent shows below are "Read more" links, not h2s, and are not read.
"""
import datetime as dt
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.la._gallery import join_name
from scrapers.nyc._common import clean, title_case
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.sikkemajenkinsco.com/current-exhibitions'
VENUE = 'Sikkema Malloy Jenkins'
_RUN = re.compile(r'^(\d{1,2})\.(\d{1,2})\s*[-–—]\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})$')


def parse_run(text):
    """(start, end) from "10.30-12.19.26" (the year is the end's), or (None, None)."""
    match = _RUN.match(clean(text))
    if not match:
        return None, None
    m1, d1, m2, d2, y = (int(g) for g in match.groups())
    year = y + 2000 if y < 100 else y
    try:
        end = dt.date(year, m2, d2)
        start = dt.date(year - 1 if m1 > m2 else year, m1, d1)
    except ValueError:
        return None, None
    return start, end


def scrape_sikkema_malloy_jenkins(env='prod', region='nyc'):
    """Scrape and process Sikkema Malloy Jenkins's current exhibitions."""
    region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Sikkema Malloy Jenkins: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for link in soup.select('h2 a[href]'):
        lines = [clean(line) for line in link.get_text('\n').split('\n') if clean(line)]
        if len(lines) < 2:
            continue
        start_date, end_date = parse_run(lines[-1])
        if not (start_date or end_date):
            continue
        names = [title_case(line) if line.isupper() else line for line in lines[:-1]]
        found += publish(env, region, VENUE, join_name(names[:2]), start_date, end_date, urljoin(PAGE_URL, link['href']),
                         tag='gallery', seen=seen)
    if not found:
        logging.warning("Sikkema Malloy Jenkins: no current exhibition found; existing data kept.")
