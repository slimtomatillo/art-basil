"""Brooklyn Museum, 200 Eastern Pkwy: the exhibitions on its listing page.

https://www.brooklynmuseum.org/exhibitions answers GitHub's servers with a Vercel challenge, so it is fetched through
the ZenRows proxy (WEBSITE-121, tier 4). Each show is a list item holding a link to /exhibitions/<slug> with an h3 (the
title), a line of dates ("October 3, 2026–January 31, 2027") and a picture. Upcoming shows are on the same page, among
the others. The permanent galleries ("Ongoing") and long-standing spotlights ("Opened June 16, 2018") are left out.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.brooklynmuseum.org/exhibitions'
VENUE = 'Brooklyn Museum'


def scrape_brooklyn_museum(env='prod', region='nyc'):
    """Scrape and process the Brooklyn Museum's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Brooklyn Museum: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('li > a[href^="/exhibitions/"]'):
        heading = card.find('h3')
        dates_tag = heading.find_next_sibling('span') if heading else None
        if dates_tag is None:
            continue
        dates = clean(dates_tag.get_text(' '))
        if re.match(r'(?:ongoing|opened)\b', dates, re.IGNORECASE):
            continue
        start_date, end_date = parse_dates(dates, today)
        name = clean(heading.get_text(' '))
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']), tag='museum',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Brooklyn Museum: no current or upcoming exhibition found; existing data kept.")
