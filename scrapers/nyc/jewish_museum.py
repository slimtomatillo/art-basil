"""The Jewish Museum, 1109 Fifth Ave: the exhibitions on its listing page.

thejewishmuseum.org/exhibitions lists the shows as cards, each a link to the show's page whose aria-label reads
"On View, <title>, <dates>" or "Coming Soon, <title>, <dates>" ("On View, Modernity and Opulence: Women of the Wiener
Werkstätte, Jul. 17 – Nov. 15, 2026"). The cards past those (earlier shows) carry no label and are left out. A card
whose dates can't be read is skipped. The card's picture is a lazy-loaded data-src; each show's own page is linked.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://thejewishmuseum.org/exhibitions'
VENUE = 'The Jewish Museum'
_LABEL = re.compile(r'^(?:On View|Coming Soon),\s*(?P<name>.+?),\s*(?P<dates>[A-Z][a-z]{2,8}\.?\s+\d{1,2}(?:,\s*\d{4})?\s*[–-]\s*'
                    r'[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s*\d{4})$')


def scrape_jewish_museum(env='prod', region='nyc'):
    """Scrape and process the Jewish Museum's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Jewish Museum: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.find_all('a', attrs={'aria-label': re.compile(r'^(?:On View|Coming Soon),')}):
        match = _LABEL.match(clean(card['aria-label']))
        if not match:
            continue
        start_date, end_date = parse_dates(match['dates'], today)
        if not (start_date or end_date):
            continue
        name = re.sub(r'\s*<br\s*/?>\s*', ': ', match['name'])           # "Art in Focus<br>Oded Halahmy: ..." (a line break)
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']),
                         tag='museum', seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Jewish Museum: no current or upcoming exhibition found; existing data kept.")
