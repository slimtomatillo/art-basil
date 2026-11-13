"""Pace Gallery, 540 W 25th St: the New York exhibitions on its listing page.

https://www.pacegallery.com/exhibitions/ lists Pace's shows in every city (New York, London, Los Angeles, Seoul,
Tokyo...) as cards: the artist (h3), a status ("On View", "Upcoming"), the show's title, the run ("Nov 6 – Dec 19,
2026") and the city. Only cards whose city is New York are kept; the name is "Artist: Title". Each show's own page is
linked; descriptions.py reads it.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.pacegallery.com/exhibitions/'
VENUE = 'Pace Gallery'


def _text(card, selector):
    tag = card.select_one(selector)
    return clean(tag.get_text(' ')) if tag else ''


def scrape_pace_gallery(env='prod', region='nyc'):
    """Scrape and process Pace's New York exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Pace Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a.index-grid__link'):
        if _text(card, '.index-grid__text-location').lower() != 'new york':
            continue
        artist, title = _text(card, '.index-grid__text-title'), _text(card, '.index-grid__text-subtitle')
        name = f'{artist}: {title}' if artist and title else (title or artist)
        start_date, end_date = parse_dates(_text(card, '.index-grid__text-date'), today)
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']), tag='gallery',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Pace Gallery: no New York exhibition found; existing data kept.")
