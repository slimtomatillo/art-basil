from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, index_of
from processing import region_today
import logging

HOME_URL = 'https://www.kohngallery.com/'
VENUE = 'Kohn Gallery'


def scrape_kohn_gallery(env='prod', region='la'):
    """Scrape and process the shows on view at Kohn Gallery (the home page lists them, each with an end date only)."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Kohn Gallery: could not fetch the home page; existing data kept.")
        return
    lines = page_lines(soup)
    # "Artist | On view through December 19 | Gallery 1 & 2", then the press list below
    end = index_of(lines, 'RECENT PRESS', len(lines))
    listing = Listing(env, region, VENUE, soup, HOME_URL)
    for parts, start, finish, _ in dated_headings(lines, today, end=end, stops=('CONTACT', 'Menu'), limit=1, after=1):
        if parts:
            listing.add(parts[0], start, finish)
    if not listing.publish():
        logging.warning("Kohn Gallery: no exhibitions found; existing data kept.")
