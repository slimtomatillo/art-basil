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
# The labels of the venue's addresses in nyc_venues.json (WEBSITE-122). The listing gives only the city, but a show's own page prints
# its space under a "GALLERY" line ("540 West 25th Street", "508 & 510 West 25th Street", "125 Newbury" and "395 Broadway").
SPACES = ('540 West 25th Street', '508 & 510 West 25th Street', '125 Newbury (395 Broadway)')


def show_space(soup):
    """The label of the space a show's page names after its "GALLERY" line, or None."""
    lines = [clean(text) for text in soup.stripped_strings]
    for line, following in zip(lines, lines[1:]):
        if line.upper() == 'GALLERY':
            for label in SPACES:
                if label.lower().startswith(following.lower()) and following:
                    return label
    return None


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
        url = urljoin(PAGE_URL, card['href'])
        page = None if end_date and end_date < today else fetch_and_parse(url)        # a past show is dropped, so its page is not fetched
        space = show_space(page) if page is not None else None
        found += publish(env, region, VENUE, name, start_date, end_date, url, tag='gallery',
                         seen=seen, image=card_picture(card, PAGE_URL), locations=[space] if space else None)
    if not found:
        logging.warning("Pace Gallery: no New York exhibition found; existing data kept.")
