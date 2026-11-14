"""Scrapers for venues whose listing links to a page per show (WEBSITE-121).

Most museum sites list their exhibitions as cards that carry only a title and a picture; the dates and the
description are on each show's own page. read_show() reads one such page (its title, its dates from the first
short date line, a description and a picture) and scrape_show_pages() runs it for every show a listing links to.
A show whose page has no readable date line ("Ongoing", a permanent display) is left out, and one that has ended is
dropped by publish().
"""
import logging
import re
from urllib.parse import urljoin, urlparse

import images
from processing import region_today
from scrapers.la._gallery import date_label
from scrapers.nyc._common import clean, numeric_run
from scrapers.tor._common import publish
from utils import fetch_and_parse

_WEEKDAY = re.compile(r'\b(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+', re.IGNORECASE)
_PERMANENT_AFTER_DAYS = 400       # a show with a start date this old and no end date is a standing display
_DATE_LINES = 160                  # the dates are near the top of a show's page; later ones are events and captions
_NOT_SHOWS = re.compile(r'/(?:past|archive|archives|upcoming|current|previous|traveling|digital|virtual|online)'
                        r'(?:[-_/][a-z-]*)?/?$', re.IGNORECASE)


def _meta(soup, **attrs):
    tag = soup.find('meta', attrs=attrs)
    return clean(tag.get('content')) if tag and tag.get('content') else ''


def show_links(soup, page_url, pattern, limit=40):
    """Absolute links to shows' own pages on a listing: those whose address matches `pattern`, once each, leaving out
    the section links (past, archive...) and the listing itself."""
    wanted = re.compile(pattern)
    listing = urlparse(page_url).path.rstrip('/')
    site = urlparse(page_url).netloc.lower().removeprefix('www.')
    found = []
    for a in soup.find_all('a', href=True):
        url = urljoin(page_url, a['href']).split('#')[0].split('?')[0]
        parts = urlparse(url)
        if parts.netloc.lower().removeprefix('www.') != site:
            continue                                         # another site's page is never one of this venue's shows
        if not wanted.search(parts.path) or parts.path.rstrip('/') == listing or _NOT_SHOWS.search(parts.path):
            continue
        if url.rstrip('/') not in [u.rstrip('/') for u in found]:          # the same page with and without a trailing slash
            found.append(url)
    return found[:limit]


def _title(soup, suffix):
    for candidate in (_meta(soup, property='og:title'), clean(soup.title.get_text(' ')) if soup.title else '',
                      clean(soup.find('h1').get_text(' ')) if soup.find('h1') else ''):
        name = candidate.strip()
        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)].strip()
        if name:
            return name
    return ''


def _description(soup, name):
    """The show's description, by the rules descriptions.py applies (the page's own summary, else its first real
    paragraphs); None if none passes."""
    import descriptions                                  # imported here: it imports modules that import the scrapers
    for source, text in descriptions.candidates(soup):
        text = descriptions.strip_opening_furniture(descriptions.strip_title_heading(text, name))
        if descriptions.usable(text, name):
            return descriptions.trim(text)
    return None


def _picture(soup, url):
    """The page's share picture, if it is an address a browser can load (one site writes it without a slash)."""
    picture = _meta(soup, property='og:image')
    if not picture or ' ' in picture:
        return None
    picture = urljoin(url, picture)
    return images.secure_image_url(picture) if images.plausible_image_url(picture) else None


def read_show(url, today, fetch=fetch_and_parse, suffix=''):
    """{name, start, end, description, image} from a show's own page, or None (unreachable, or no date line)."""
    soup = fetch(url)
    if soup is None:
        return None
    name = _title(soup, suffix)
    page = fetch_copy(soup)
    lines = [clean(line) for line in page.get_text('\n').split('\n') if clean(line)]
    dates = None
    for line in lines[:_DATE_LINES]:
        dates = date_label(_WEEKDAY.sub('', line), today)
        if not dates:
            run = numeric_run(line)                 # "10.08.26 - 12.12.26" (BRIC)
            dates = run if run[0] or run[1] else None
        if dates:
            break
    if not (name and dates):
        return None
    if dates[1] is None and dates[0] and (today - dates[0]).days > _PERMANENT_AFTER_DAYS:
        return None                  # open since long ago with no end: an online or permanent display, not a show
    return {'name': name, 'start': dates[0], 'end': dates[1], 'description': _description(soup, name),
            'image': _picture(soup, url)}


def fetch_copy(soup):
    """A copy of the page without scripts and styles, for reading its text."""
    from bs4 import BeautifulSoup
    copy = BeautifulSoup(str(soup), 'html.parser')
    for tag in copy(['script', 'style', 'noscript']):
        tag.decompose()
    return copy


def scrape_show_pages(env, region, venue, listings, pattern, fetch=fetch_and_parse, today=None, suffix='', tag='museum'):
    """Read every show a venue's listing page(s) link to and publish it. Returns how many were stored."""
    today = today or region_today(region)
    found = 0
    seen = set()
    links = []
    for listing in listings:
        soup = fetch(listing)
        if soup is None:
            logging.warning(f"{venue}: could not fetch {listing}; existing data kept.")
            continue
        links += [url for url in show_links(soup, listing, pattern) if url not in links]
    for url in links:
        show = read_show(url, today, fetch=fetch, suffix=suffix)
        if show is None:
            continue
        found += publish(env, region, venue, show['name'], show['start'], show['end'], url, tag=tag,
                         description=show['description'], seen=seen, image=show['image'])
    if not found:
        logging.warning(f"{venue}: no current or upcoming exhibition found; existing data kept.")
    return found
