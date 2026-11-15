"""Gagosian: the New York exhibitions on its Current and Upcoming pages.

https://gagosian.com/exhibitions/ and /exhibitions/upcoming/ answer GitHub's servers with a Cloudflare challenge, so
they are fetched through the ZenRows proxy (WEBSITE-121, tier 4). They list Gagosian's shows in every city as links to
/exhibitions/<year>/<slug>/. A card has an h4 (the artist in bold, then the title after a line break, when there is
one), optionally a "Curated by" line, the dates in two spans and the place ("980 Madison at 76th Street, New York",
"Beverly Hills", "Davies Street, London"). Only cards whose place ends in "New York" are kept, and each is stored with
the space it names, as for the other New York galleries with several.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGES = ['https://gagosian.com/exhibitions/', 'https://gagosian.com/exhibitions/upcoming/']
VENUE = 'Gagosian'
# (label, regex for the place line); the addresses are in docs/data/nyc_venues.json under the same labels
SPACES = [
    ('980 Madison', r'980 Madison'),
    ('Park & 75', r'Park & 75'),
    ('555 West 24th', r'555 West 24th'),
    ('541 West 24th', r'541 West 24th'),
    ('West 21st Street', r'West 21st'),
    ('West 18th Street', r'West 18th'),
]


def _read(card):
    """(name, date text, place) from a card, or None."""
    heading = card.find('h4')
    if heading is None:
        return None
    artist_tag = heading.find('b')
    artist = clean(artist_tag.get_text(' ')) if artist_tag else ''
    if artist_tag:
        artist_tag.extract()
    title = clean(heading.get_text(' '))
    paragraphs = [clean(p.get_text('')) for p in card.find_all('p')]
    paragraphs = [p for p in paragraphs if p and not p.lower().startswith('curated by')]
    if len(paragraphs) < 2:
        return None
    name = f'{artist}: {title}' if artist and title else (artist or title)
    return name, paragraphs[0], paragraphs[-1]


def scrape_gagosian(env='prod', region='nyc'):
    """Scrape and process Gagosian's New York exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    for page_url in PAGES:
        soup = fetch_and_parse(page_url)
        if soup is None:
            logging.warning(f"Gagosian: could not fetch {page_url}; existing data kept.")
            continue
        for card in soup.find_all('a', href=re.compile(r'/exhibitions/20\d\d/')):
            picture = card_picture(card, page_url)
            read = _read(card)
            if read is None:
                continue
            name, dates, place = read
            if not place.lower().endswith('new york'):
                continue
            start_date, end_date = parse_dates(dates, today)
            if not (name and (start_date or end_date)):
                continue
            spaces = [label for label, pattern in SPACES if re.search(pattern, place, re.IGNORECASE)] or None
            found += publish(env, region, VENUE, name, start_date, end_date, urljoin(page_url, card['href']), tag='gallery',
                             seen=seen, image=picture, locations=spaces)
    if not found:
        logging.warning("Gagosian: no New York exhibition found; existing data kept.")
