"""Chandler Gallery, 1111 Geary Blvd, San Francisco (Lower Nob Hill): chandler-gallery.com (WEBSITE-130).

The gallery opened in Mill Valley in 2025 and its permanent San Francisco space on 2026-11-14; in between it showed at
Minnesota Street Project. /exhibitions/ is an Artlogic list: an <li> per show with an h2, a span.subtitle, a span.date
written day first ("14 November - 18 December 2026") and a link to the show's page, in On view, Upcoming and Past sections
(the dates say which, so the sections are not read). The h2 and the subtitle swap roles from show to show: a recent solo
show has the artist in the h2 and "Grounding  |  A Solo Exhibition at 1111 Geary" in the subtitle, an upcoming one has the
artist and "At 1111 Geary", an older one the title and then the artist. A show whose subtitle puts it somewhere else ("A
Group Exhibition at Minnesota Street Project") is left out: it is shown under that venue, not on Geary Street. The
description and the picture come from each show's own page (the listing's description is cut short).
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._pages import _description, _picture
from scrapers.sf._artlogic import parse_day_first_range
from scrapers.tor._common import publish
from utils import fetch_and_parse

LIST_URL = 'https://chandler-gallery.com/exhibitions/'
VENUE = 'Chandler Gallery'
_PLACE = re.compile(r'\bat\s+(.+)$', re.IGNORECASE)
_DESCRIPTOR = re.compile(r'^(?:an?\s+)?(?:solo|group|two-person|inaugural)\b', re.IGNORECASE)


def split_subtitle(subtitle):
    """(title, place) from a subtitle: "Grounding  |  A Solo Exhibition at 1111 Geary" gives ("Grounding", "1111 Geary"),
    "At 1111 Geary" gives ("", "1111 Geary"), "Mari Andrews" gives ("Mari Andrews", ""). A part that only describes the show
    ("A Group Exhibition") is no title."""
    title, place = '', ''
    for part in [' '.join(p.split()) for p in (subtitle or '').split('|')]:
        found = _PLACE.search(part)
        if found:
            place = found.group(1).strip()
        elif part and not title and not _DESCRIPTOR.match(part):
            title = part
    return title, place


def read_shows(soup, base_url=LIST_URL):
    """Yield (name, start, end, page url) for each show at 1111 Geary on the list; those at another place, and those whose
    dates cannot be read, are left out."""
    for li in soup.select('li'):
        heading = li.select_one('.content h2')
        date = li.select_one('.content .date')
        link = li.find('a', href=True)
        if not (heading and date and link):
            continue
        title, place = split_subtitle(li.select_one('.content .subtitle').get_text(' ') if li.select_one('.content .subtitle') else '')
        if place and not place.lower().startswith('1111 geary'):
            continue
        name = ' '.join(heading.get_text(' ').split())
        if title:
            name = f'{name}: {title}'
        start, end = parse_day_first_range(' '.join(date.get_text(' ').split()))
        if not (start and end):
            logging.warning(f"Chandler Gallery: no readable dates for {name!r}")
            continue
        yield name, start, end, urljoin(base_url, link['href'])


def scrape_chandler_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions at Chandler Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(LIST_URL)
    if soup is None:
        logging.warning("Chandler Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for name, start, end, url in read_shows(soup):
        if end < today:
            continue                                         # past shows are not fetched
        page = fetch_and_parse(url)
        found += publish(env, region, VENUE, name, start, end, url, tag='gallery',
                         description=_description(page, name) if page is not None else None,
                         image=_picture(page, url) if page is not None else None, seen=seen)
    if not found:
        logging.warning("Chandler Gallery: no current or upcoming exhibition found; existing data kept.")
