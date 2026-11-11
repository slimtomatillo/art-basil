"""Chinese Culture Center of San Francisco, CCC Art Center at 667 Grant Ave (the office is at 750 Kearny St): the exhibitions on its "Current Exhibitions" page.

https://www.cccsf.us/current-exhibitions is a Wix blog list. Each post has a title, a one-line
description that is just the dates ("February 14, 2026 - Ongoing") and a category label
(EXHIBITION, PUBLIC ART). Only EXHIBITION posts are kept: the public-art murals are outdoors and
not gallery shows. An open-ended show is marked ongoing. (The "Upcoming Events" page lists
programs, not exhibitions, and is not read.)
"""
import logging
import re

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.cccsf.us/current-exhibitions'
VENUE = 'Chinese Culture Center of San Francisco'
_ONGOING = re.compile(r'[\s\-–—]*ongoing\s*$', re.IGNORECASE)


def _hook(item, hook):
    tag = item.select_one(f'[data-hook="{hook}"]')
    return ' '.join(tag.get_text(' ').split()) if tag else ''


def scrape_chinese_culture_center(env='prod', region='sf'):
    """Scrape and process the exhibitions on the Chinese Culture Center's current-exhibitions page."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Chinese Culture Center: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for item in soup.select('[data-hook="post-list-item"]'):
        if _hook(item, 'post-category-label').upper() != 'EXHIBITION':
            continue
        link = item.find('a', href=True)
        name = _hook(item, 'post-title')
        text = _hook(item, 'post-description')
        ongoing = bool(_ONGOING.search(text))
        start_date, end_date = parse_date_text(_ONGOING.sub('', text) if ongoing else text, today)
        if ongoing:
            end_date = None
        if not (name and link and (start_date or end_date)):
            logging.warning(f"Chinese Culture Center: no readable dates for {name!r} ({text!r})")
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, link['href'], tag='gallery',
                         seen=seen, ongoing=ongoing)
    if not found:
        logging.warning("Chinese Culture Center: no current exhibition found; existing data kept.")
