"""Whitney Museum of American Art, 99 Gansevoort St: the exhibitions on its listing page.

https://whitney.org/exhibitions lists the shows as cards: a link to the show's own page holding a title
(.list-item__title) and a line that is the run or the opening ("Through May 10, 2027", "Opens Nov 21"). A show
whose line has no day ("Through Spring 2027", "2026") or no line at all (a collection installation) can't be
dated and is left out. The page carries no blurbs; each show's own page is linked, and descriptions.py reads it.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://whitney.org/exhibitions'
VENUE = 'Whitney Museum of American Art'


def scrape_whitney(env='prod', region='nyc'):
    """Scrape and process the Whitney's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Whitney: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a[href^="/exhibitions/"]'):
        title = card.select_one('.list-item__title')
        subtitle = card.select_one('.list-item__subtitle')
        if title is None or subtitle is None:
            continue
        name = clean(title.get_text(' '))
        start_date, end_date = parse_dates(subtitle.get_text(' '), today)
        if not (start_date or end_date):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']),
                         tag='museum', seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Whitney: no current or upcoming exhibition found; existing data kept.")
