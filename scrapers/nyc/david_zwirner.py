"""David Zwirner, New York (West 19th and 20th Streets, Chelsea, and Tribeca): its New York exhibitions.

https://www.davidzwirner.com/exhibitions lists the gallery's shows in every city (New York, Los Angeles, London, Paris,
Hong Kong) as cards, under "Currently on View" and "Upcoming". A card holds the artist, a second line with the show's
title when it has one, the place ("New York: 19th Street, New York: 20th Street", "London") and the run ("Now Open:
November 5—December 12, 2026", "Coming Soon: ..."); a link over the card goes to the show's page. Only cards whose
place starts with "New York" are kept. The "Featured" carousel at the top repeats shows, which are stored once.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.davidzwirner.com/exhibitions'
VENUE = 'David Zwirner'
_PLACE = re.compile(r'^(?:New York|Los Angeles|London|Paris|Hong Kong)\b')


def _lines(card):
    """The card's text lines, each once (the artist's name is repeated for the picture and the link)."""
    lines = []
    for text in card.stripped_strings:
        text = clean(text)
        if text and text not in lines and text.lower() not in ('learn more', 'arrow left icon', 'arrow right icon'):
            lines.append(text)
    return lines


def scrape_david_zwirner(env='prod', region='nyc'):
    """Scrape and process David Zwirner's New York exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("David Zwirner: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for link in soup.select('a.absolute.inset-0[href^="/exhibitions/"]'):
        card = link.parent
        lines = _lines(card)
        place_at = next((i for i, line in enumerate(lines) if _PLACE.match(line)), None)
        if place_at is None or not lines[place_at].startswith('New York') or place_at + 1 >= len(lines) or place_at == 0:
            continue
        name = ': '.join(lines[:place_at])
        start_date, end_date = parse_dates(lines[place_at + 1], today)
        if not (start_date or end_date):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']), tag='gallery',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("David Zwirner: no New York exhibition found; existing data kept.")
