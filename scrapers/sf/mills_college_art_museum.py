"""Mills College Art Museum at Northeastern University, 5000 MacArthur Blvd, Oakland (always free).

The exhibitions page has a block for each show under a "CURRENT" or "UPCOMING" heading: the picture,
the run as a heading ("SEP 12-DEC 6, 2026"), the title as a link to the show's page, and a one-line
description. The site answers Cloudflare's 403 to scripted requests, so it is fetched through the ZenRows
proxy (utils.PROXY_DOMAINS). Past shows are on a separate collection site and are not read.
"""
import logging
from urllib.parse import urljoin

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://mcam.oakland.northeastern.edu/exhibitions/'
VENUE = 'Mills College Art Museum'


def _text(tag):
    return ' '.join(tag.get_text(' ').split()) if tag is not None else ''


_SMALL_WORDS = {'a', 'an', 'and', 'at', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}


def _title_case(text):
    """The site prints titles in capitals ("THE DATA AT HAND: ..."); put them in title case, leaving
    a title that already has lower-case letters alone."""
    if not text.isupper():
        return text
    words = text.lower().split(' ')
    return ' '.join(w if (i and w in _SMALL_WORDS and not words[i - 1].endswith(':')) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def scrape_mills_college_art_museum(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions of the Mills College Art Museum."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Mills College Art Museum: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for status in soup.select('h2.status'):
        block = status.parent
        link = block.select_one('h3 a[href]')
        date_tag = block.select_one('h2.h2title')
        if link is None or date_tag is None:
            continue
        name = _title_case(_text(link))
        # the date heading can be split across tags ("JAN 19-MAY 9, 202" + "7"), so read all its text
        start_date, end_date = parse_date_text(_text(date_tag), today)
        if not (start_date or end_date):
            logging.warning(f"Mills College Art Museum: no readable dates for {name!r} ({_text(date_tag)!r})")
            continue
        description = _text(block.select_one('p.more')) or None
        picture = block.select_one('figure img[src]')
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']),
                         tag='museum', description=description, seen=seen,
                         image=urljoin(PAGE_URL, picture['src']) if picture else None)
    if not found:
        logging.warning("Mills College Art Museum: no current or upcoming exhibitions found; existing data kept.")
