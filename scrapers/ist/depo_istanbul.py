from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.depoistanbul.net/sergiler/'
VENUE = 'DEPO'


def scrape_depo_istanbul(env='prod', region='ist'):
    """Scrape and process the exhibitions at DEPO (the Turkish page, newest first)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("DEPO: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # "Title | 22 Eylül – 21 Kasım 2026"; some shows also have a Kurdish or Armenian title and date line first,
    # which are not read (their month names aren't ones we know)
    seen = set()
    for parts, start, end, _ in dated_headings(lines, today, stops=('Sergiler', 'Menüyü Aç/Kapat'), limit=1):
        # the archive runs back to 2010 and has a few one-day entries; a lone date would read as an open-ended show
        if parts and start and end:
            listing.add(parts[0], start, end, tag='gallery', seen=seen)
    if not listing.publish():
        logging.warning("DEPO: no exhibitions found; existing data kept.")
