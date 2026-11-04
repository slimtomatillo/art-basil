from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.cjamesgallery.com/exhibitions'
VENUE = 'Charlie James Gallery'
STOPS = ('Read more →', 'Featured', 'UPCOMING', 'PAST', 'EXHIBITIONS')


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
    for parts, start, end, _ in dated_headings(lines, today, stops=STOPS, limit=3, after=1):
        name = _name(parts)
        if name:
            listing.add(name, start, end, anchor=parts[0], seen=seen)
    if not listing.publish():
        logging.warning("Charlie James Gallery: no exhibitions found; existing data kept.")
