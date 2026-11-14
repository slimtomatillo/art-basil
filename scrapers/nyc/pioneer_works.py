"""Pioneer Works, 159 Pioneer St, Red Hook, Brooklyn: the exhibitions at pioneerworks.org/exhibitions.

The page is sections of text: "Current Exhibitions" (each show is three lines: the run, the title and the artists),
then "On View" (long-term works marked "ONGOING", left out) and "Past Exhibitions". Each show is also a link
(/exhibitions/<slug>) holding its title and artists. A show with one artist is named "Artist: Title"; one with several
("Finnegan Shannon, with Joselia Rebekah Hughes, ...") is named by its title.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import page_lines, publish
from utils import fetch_and_parse

PAGE_URL = 'https://pioneerworks.org/exhibitions'
VENUE = 'Pioneer Works'
_STARTS = ('current exhibition', 'upcoming exhibition')
_ENDS = ('on view', 'past exhibition')


def _name(title, artists):
    one_artist = artists and ',' not in artists and ' with ' not in artists and ' and ' not in artists and len(artists) <= 45
    return f'{artists}: {title}' if one_artist else title


def scrape_pioneer_works(env='prod', region='nyc'):
    """Scrape and process Pioneer Works' current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Pioneer Works: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    begin = next((i for i, line in enumerate(lines) if line.lower().startswith(_STARTS)), None)
    if begin is None:
        logging.warning("Pioneer Works: no Current Exhibitions section found; existing data kept.")
        return
    end = next((i for i in range(begin + 1, len(lines)) if lines[i].lower() in _ENDS), len(lines))
    cards = {}                                   # title -> the link around its text; pictures: link -> its picture
    pictures = {}
    for a in soup.select('a[href^="/exhibitions/"]'):
        strings = [clean(t) for t in a.stripped_strings]
        if strings:
            cards[strings[0]] = a
        elif a.find('img'):
            pictures.setdefault(a['href'], card_picture(a, PAGE_URL))
    found = 0
    seen = set()
    section = lines[begin + 1:end]
    i = 0
    while i < len(section):
        start_date, end_date = parse_dates(section[i], today)
        if not (start_date or end_date) or i + 1 >= len(section):
            i += 1
            continue
        title = section[i + 1]
        after = section[i + 2] if i + 2 < len(section) else ''
        artists = '' if parse_dates(after, today) != (None, None) else after       # the next show's run, not this one's artists
        card = cards.get(title)
        if card is not None:
            found += publish(env, region, VENUE, _name(title, artists), start_date, end_date, urljoin(PAGE_URL, card['href']),
                             tag='gallery', seen=seen, image=pictures.get(card['href']))
        i += 3 if artists else 2
    if not found:
        logging.warning("Pioneer Works: no current or upcoming exhibition found; existing data kept.")
