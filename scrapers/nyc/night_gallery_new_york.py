"""Night Gallery's New York viewing room (61 Lispenard St, Tribeca): its shows on the gallery's listing page.

The listing at https://www.nightgallery.ca/exhibitions (the current show; the upcoming ones are on /exhibitions/upcoming) is shared with the Los Angeles gallery and gives no city, so
the shows are read and placed by scrapers/la/night_gallery.py (each show's own page names its address); the ones in
New York are published here (WEBSITE-120).
"""
import logging

from processing import region_today
from scrapers.la.night_gallery import read_listings
from scrapers.tor._common import Listing

VENUE = 'Night Gallery New York'


def scrape_night_gallery_new_york(env='prod', region='nyc'):
    """Scrape and process the exhibitions at Night Gallery in New York."""
    today = region_today(region)
    pages = read_listings(today)
    if pages is None:
        logging.warning("Night Gallery New York: could not fetch the exhibitions page; existing data kept.")
        return
    stored = 0
    for page_url, soup, shows in pages:
        listing = Listing(env, region, VENUE, soup, page_url)
        for name, start, end, anchor, link, city in shows:
            if city == 'nyc':
                listing.add(name, start, end, link=link, anchor=anchor)
        stored += listing.publish()
    if not stored:
        logging.info("Night Gallery New York: no New York exhibition listed; existing data kept.")
