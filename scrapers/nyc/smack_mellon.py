"""Smack Mellon, 92 Plymouth St, DUMBO, Brooklyn: the exhibitions at smackmellon.org/exhibitions/.

The page's top banner is a link (a.article) to the show on view, holding a label ("— Current Exhibition", or
"— Upcoming Exhibition" when one is announced), the title and the run ("September 19-December 6, 2026"). The past
exhibitions listed below it are not read. Each show's own page is linked.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.smackmellon.org/exhibitions/'
VENUE = 'Smack Mellon'


def scrape_smack_mellon(env='prod', region='nyc'):
    """Scrape and process Smack Mellon's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Smack Mellon: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a.article[href]'):
        lines = [clean(t) for t in card.stripped_strings]
        lines = [line for line in lines if line]
        label = lines[0].lower() if lines else ''
        if len(lines) < 3 or not ('current' in label or 'upcoming' in label):
            continue
        start_date, end_date = parse_dates(lines[-1], today)
        if not (start_date or end_date):
            continue
        found += publish(env, region, VENUE, lines[1], start_date, end_date, urljoin(PAGE_URL, card['href']), tag='gallery',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Smack Mellon: no current or upcoming exhibition found; existing data kept.")
