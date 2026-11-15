"""El Museo del Barrio, 1230 Fifth Ave: the exhibitions on its listing page.

https://elmuseo.org/exhibitions/ answers GitHub's servers with a Cloudflare challenge, so it is fetched through the
ZenRows proxy (WEBSITE-121, tier 4). The page has On View, Upcoming and Past sections; every show is a card with a
picture linking to /exhibition/<slug>/, a line of dates ("April 23 – August 2, 2026") and an h3 link with the title.
All sections are read, and publish() drops the shows that have ended.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://elmuseo.org/exhibitions/'
VENUE = 'El Museo del Barrio'


def _card(heading):
    element = heading
    for _ in range(5):
        element = element.parent
        if element is None:
            return None
        if element.find('img') and len(element.find_all('h3')) == 1:
            return element
    return None


def scrape_el_museo_del_barrio(env='prod', region='nyc'):
    """Scrape and process El Museo del Barrio's exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("El Museo del Barrio: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for link in soup.select('h3 a[href*="/exhibition/"]'):
        card = _card(link.find_parent('h3'))
        if card is None:
            continue
        name = clean(link.get_text(' '))
        dates = next((clean(line) for line in card.get_text('\n').split('\n')
                      if clean(line) and any(c.isdigit() for c in line) and len(clean(line)) < 60), '')
        start_date, end_date = parse_dates(dates, today)
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']), tag='museum',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("El Museo del Barrio: no current or upcoming exhibition found; existing data kept.")
