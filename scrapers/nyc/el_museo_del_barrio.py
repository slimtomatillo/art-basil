"""El Museo del Barrio, 1230 Fifth Ave: the exhibitions on its listing page.

https://elmuseo.org/exhibitions/ answers GitHub's servers with a Cloudflare challenge, so it is fetched through the
ZenRows proxy (WEBSITE-121, tier 4). The page has On View, Upcoming and Past sections, and shows come in two kinds
of card, both read (WEBSITE-129): the past ones are a picture linking to /exhibition/<slug>/, a line of dates
("April 23 – August 2, 2026") and an h3 link with the title; the ones on view and upcoming are one
<div class="exhcard"> holding a single link around a banner, <div class="exfechas"> (the dates) and
<div class="exh-1col-name"> (the title). publish() drops the shows that have ended.
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


def read_cards(soup):
    """Yield (name, dates text, page url, card element) for each show on the page: the on-view and upcoming cards
    (div.exhcard), then the h3 cards of the past section."""
    for card in soup.select('div.exhcard'):
        link = card.find('a', href=True)
        name = card.select_one('.exh-1col-name')
        dates = card.select_one('.exfechas')
        if link and name and dates:
            yield clean(name.get_text(' ')), clean(dates.get_text(' ')), urljoin(PAGE_URL, link['href']), card
    for link in soup.select('h3 a[href*="/exhibition/"]'):
        card = _card(link.find_parent('h3'))
        if card is None:
            continue
        dates = next((clean(line) for line in card.get_text('\n').split('\n')
                      if clean(line) and any(c.isdigit() for c in line) and len(clean(line)) < 60), '')
        yield clean(link.get_text(' ')), dates, urljoin(PAGE_URL, link['href']), card


def scrape_el_museo_del_barrio(env='prod', region='nyc'):
    """Scrape and process El Museo del Barrio's exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("El Museo del Barrio: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for name, dates, url, card in read_cards(soup):
        start_date, end_date = parse_dates(dates, today)
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, url, tag='museum',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("El Museo del Barrio: no current or upcoming exhibition found; existing data kept.")
