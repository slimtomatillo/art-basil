"""The Kitchen, 512 W 19th St, Chelsea: the exhibitions on its "On View" page.

thekitchen.org/on-view/ lists everything on at The Kitchen: exhibitions and events (a gala, a performance). Each is a
link to its page (/on-view/<slug>) holding the artist, the title and the date. An exhibition has a run ("Dec 4, 2026 -
Feb 6, 2027", written as two strings); an event has a single date ("May 20"), and is left out.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://thekitchen.org/on-view/'
VENUE = 'The Kitchen'


def scrape_the_kitchen(env='prod', region='nyc'):
    """Scrape and process The Kitchen's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("The Kitchen: could not fetch the On View page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a[href^="/on-view/"]'):
        lines = [clean(t) for t in card.stripped_strings]
        lines = [line for line in lines if line]
        # [artist, title, "Dec 4, 2026", "- Feb 6, 2027"]: the run is the last two strings; an event has one date only
        if len(lines) < 3 or not lines[-1].startswith('-'):
            continue
        start_date, end_date = parse_dates(f'{lines[-2]} {lines[-1]}', today)
        if not (start_date and end_date):
            continue
        name = ': '.join(lines[:-2])
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']), tag='gallery',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("The Kitchen: no current or upcoming exhibition found; existing data kept.")
