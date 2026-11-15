"""The Metropolitan Museum of Art, 1000 Fifth Ave: the exhibitions on its listing page.

https://www.metmuseum.org/exhibitions answers GitHub's servers with a Vercel challenge, so it is fetched through the
ZenRows proxy (WEBSITE-121, tier 4). The page lists each show as an <article> card: a picture, the title (a link to the
show's page) and one line of dates ("Through January 31, 2027", "November 24, 2026–January 6, 2027", "Ongoing"). The
Current and Upcoming sections are on the one page, and the permanent galleries ("Ongoing", "Reopens–Spring 2027") are
left out because they have no run. The same show can appear in two sections; it is stored once.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.metmuseum.org/exhibitions'
VENUE = 'The Metropolitan Museum of Art'


def _picture(card):
    """The card's picture, at a width a page can use (the site serves it at 3840 pixels)."""
    url = card_picture(card, PAGE_URL)
    return re.sub(r'([?&])w=\d+', r'\1w=1200', url) if url else url


def scrape_metropolitan_museum_of_art(env='prod', region='nyc'):
    """Scrape and process the Met's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("The Metropolitan Museum of Art: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.find_all('article'):
        link = card.find('a', href=re.compile(r'^/exhibitions/[^/]+'))
        meta = card.select_one('[class*="_meta"]')
        title = card.select_one('[class*="_title"]')
        if link is None or meta is None or title is None:
            continue
        dates = clean(meta.get_text(' '))
        if 'ongoing' in dates.lower():
            continue                                            # a permanent gallery, not a show
        start_date, end_date = parse_dates(dates, today)
        name = clean(title.get_text(' '))
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']), tag='museum',
                         seen=seen, image=_picture(card))
    if not found:
        logging.warning("The Metropolitan Museum of Art: no current or upcoming exhibition found; existing data kept.")
