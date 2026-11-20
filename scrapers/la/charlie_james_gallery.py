import logging
import re

import images
from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today

EXHIBITIONS_URL = 'https://www.cjamesgallery.com/exhibitions'
VENUE = 'Charlie James Gallery'
STOPS = ('Read more →', 'Featured', 'UPCOMING', 'PAST', 'EXHIBITIONS')
# The listing does not say which of the two galleries a show is in, but each show's own page prints its address on the line before its
# dates ("961 Chung King Road", then "november 6 - December 19, 2026"); the footer lists both. By street number, with the labels of
# the venue's addresses in la_venues.json (WEBSITE-122).
SPACES = {'969': 'Gallery 1', '961': 'Gallery 2'}
_DATE_LINE = re.compile(r'^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d', re.IGNORECASE)


def show_space(page):
    """"Gallery 1" or "Gallery 2" from the address line just above a show page's dates, or None."""
    lines = page_lines(page)
    for line, following in zip(lines, lines[1:]):
        found = re.fullmatch(r'(\d+) Chung King Road', line)
        if found and _DATE_LINE.match(following):
            return SPACES.get(found.group(1))
    return None


def _name(parts):
    """A solo show reads "Title | Artist | Title | dates"; a curated one "Title | Title | Curated by X | dates"."""
    if len(parts) == 3 and parts[0] == parts[2]:
        return f"{parts[1]}: {parts[0]}"
    return parts[0] if parts else None


def scrape_charlie_james_gallery(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Charlie James Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Charlie James Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    seen = set()  # the page lists a featured show a second time
    shows = [(parts, start, end) for parts, start, end, _ in dated_headings(lines, today, stops=STOPS, limit=3, after=1) if _name(parts)]
    links = images.card_links(soup, EXHIBITIONS_URL, [parts[0] for parts, _, _ in shows])
    for parts, start, end in shows:
        space = None
        if links.get(parts[0]) and not (end and end < today):          # a past show's page is not fetched
            page = fetch_and_parse(links[parts[0]])
            space = show_space(page) if page is not None else None
        listing.add(_name(parts), start, end, anchor=parts[0], seen=seen, locations=[space] if space else None)
    if not listing.publish():
        logging.warning("Charlie James Gallery: no exhibitions found; existing data kept.")
