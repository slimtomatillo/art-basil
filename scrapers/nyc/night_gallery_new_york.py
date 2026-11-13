"""Night Gallery's New York viewing room (61 Lispenard St, Tribeca): its shows on the gallery's listing page.

The listing at https://www.nightgallery.ca/exhibitions is shared with the Los Angeles gallery and gives no city, so
the shows are read and placed by scrapers/la/night_gallery.py (each show's own page names its address); the ones in
New York are published here (WEBSITE-120).
"""
import logging

from processing import region_today
from scrapers.la.night_gallery import EXHIBITIONS_URL, read_shows
from scrapers.tor._common import Listing
from utils import fetch_and_parse

VENUE = 'Night Gallery New York'


def scrape_night_gallery_new_york(env='prod', region='nyc'):
    """Scrape and process the exhibitions at Night Gallery in New York."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Night Gallery New York: could not fetch the exhibitions page; existing data kept.")
        return
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for name, start, end, anchor, link, city in read_shows(soup, today):
        if city == 'nyc':
            listing.add(name, start, end, link=link, anchor=anchor)
    if not listing.publish():
        logging.info("Night Gallery New York: no New York exhibition listed; existing data kept.")
