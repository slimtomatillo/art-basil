"""Dia Art Foundation: the exhibitions at Dia Chelsea (537 W 22nd St).

https://diaart.org/exhibition/exhibitions-projects answers GitHub's servers (and a plain script) with a Cloudflare
challenge, and needs page rendering through the ZenRows proxy (WEBSITE-121; the address /exhibitions is a 404). The page
lists Dia's sites in every place (Dia Beacon, Dia Bridgehampton, touring shows, permanent works) as figures: a picture,
an h2 with the title and a line "October 10, 2026–June 12, 2028, Dia Beacon" or "Opening December 4, 2026, Dia Chelsea".
Only the shows at Dia Chelsea are kept; the permanent works in the city (the Earth Room, the Broken Kilometer) have no
run and are left out.
"""
import logging
import re
from urllib.parse import quote, urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://diaart.org/exhibition/exhibitions-projects'
VENUE = 'Dia Chelsea'
_PLACE = re.compile(r',\s*Dia Chelsea\s*$', re.IGNORECASE)


def _picture(figure):
    url = card_picture(figure, PAGE_URL)
    if not url:
        return None
    parts = url.split('//', 1)
    return parts[0] + '//' + quote(parts[1], safe='/:?&=%')          # "shot27 1.jpg" has a space in its name


def scrape_dia_art_foundation(env='prod', region='nyc'):
    """Scrape and process the exhibitions at Dia Chelsea."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Dia Chelsea: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for figure in soup.find_all('figure'):
        caption = figure.find('figcaption')
        link = figure.find('a', href=True)
        if caption is None or link is None or caption.find('h2') is None:
            continue
        paragraphs = [clean(p.get_text(' ')) for p in caption.find_all('p') if p.find_parent('h2') is None]
        line = paragraphs[-1] if paragraphs else ''
        if not _PLACE.search(line):
            continue                                            # Beacon, Bridgehampton, touring shows, other cities
        dates = re.sub(r'^opening\b\s*', 'Opens ', _PLACE.sub('', line), flags=re.IGNORECASE)
        start_date, end_date = parse_dates(dates, today)
        name = clean(caption.find('h2').get_text(' '))
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']), tag='museum',
                         seen=seen, image=_picture(figure))
    if not found:
        logging.warning("Dia Chelsea: no current or upcoming exhibition found; existing data kept.")
