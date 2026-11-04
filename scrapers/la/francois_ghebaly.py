from utils import fetch_and_parse
from scrapers.sf._artlogic import artlogic_items
from scrapers.tor._common import Listing
from date_parsing import parse_date_text
from processing import region_today
import logging

URLS = ['https://ghebaly.com/exhibitions/current/', 'https://ghebaly.com/exhibitions/upcoming/']
VENUE = 'François Ghebaly'


def scrape_francois_ghebaly(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at François Ghebaly (Los Angeles and Beverly Hills)."""
    today = region_today(region)
    seen = set()
    fetched = stored = 0
    for url in URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        fetched += 1
        listing = Listing(env, region, VENUE, soup, url)
        # Month-first dates ("November 4 - December 12, 2026"); each item names its street address
        for item in artlogic_items(soup, url):
            start, end = parse_date_text(item['date_text'], today)
            if start or end:
                listing.add(item['name'], start, end, link=item['link'], seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("François Ghebaly: could not fetch the exhibitions pages; existing data kept.")
    elif not stored:
        logging.warning("François Ghebaly: no exhibitions found; existing data kept.")
