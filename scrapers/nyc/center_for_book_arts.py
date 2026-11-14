"""Center for Book Arts, 28 W 27th St: the exhibitions at centerforbookarts.org/exhibitions.

The listing shows the current exhibition as a link (/exhibitions/<slug>) holding a label ("Exhibitions →"), the title
and the run ("Sep 10–Dec 12, 2026"); earlier ones are reached by a toggle on the page and are not read.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://centerforbookarts.org/exhibitions'
VENUE = 'Center for Book Arts'


def scrape_center_for_book_arts(env='prod', region='nyc'):
    """Scrape and process the Center for Book Arts' current exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Center for Book Arts: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a[href*="/exhibitions/"]'):
        lines = [clean(t) for t in card.stripped_strings]
        lines = [line for line in lines if line and not line.startswith('Exhibitions')]
        if len(lines) < 2:
            continue
        start_date, end_date = parse_dates(lines[-1], today)
        if not (start_date or end_date):
            continue
        found += publish(env, region, VENUE, ': '.join(lines[:-1]), start_date, end_date, urljoin(PAGE_URL, card['href']),
                         tag='gallery', seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Center for Book Arts: no current exhibition found; existing data kept.")
