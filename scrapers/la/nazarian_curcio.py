from utils import fetch_and_parse
from scrapers.sf._artlogic import artlogic_items
from scrapers.tor._common import Listing
from date_parsing import parse_date_text
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://nazariancurcio.com/exhibitions'
# Shulamit Nazarian renamed the gallery Nazarian / Curcio; the old shulamitgallery.com redirects here
VENUE = 'Nazarian / Curcio'


def scrape_nazarian_curcio(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Nazarian / Curcio."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Nazarian / Curcio: could not fetch the exhibitions page; existing data kept.")
        return
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # The Artlogic list runs back through every past show, which publish() leaves out;
    # dates are written month-first ("November 7 - December 19, 2026")
    for item in artlogic_items(soup, EXHIBITIONS_URL):
        start, end = parse_date_text(item['date_text'], today)
        if start or end:
            listing.add(item['name'], start, end, link=item['link'], tag='gallery')
    if not listing.publish():
        logging.warning("Nazarian / Curcio: no exhibitions found; existing data kept.")
