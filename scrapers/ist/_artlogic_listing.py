"""Shared reading of an Artlogic exhibitions list for the Istanbul galleries (see scrapers/sf/_artlogic.py).
Dates there are day-first English ("16 Sep - 7 Nov 2026"). Some galleries list their other cities' shows
on the same page; each item names its city in span.location."""
from utils import fetch_and_parse
from scrapers.sf._artlogic import artlogic_items, parse_day_first_range
from scrapers.tor._common import Listing
from processing import region_today
import logging


def scrape_artlogic_listing(env, region, venue, url, city_marker=None):
    """Publish the shows of one Artlogic list page. `city_marker` (e.g. 'stanbul') keeps only items whose
    location contains it; items without a location are kept."""
    region_today(region)
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning(f"{venue}: could not fetch the exhibitions page; existing data kept.")
        return
    listing = Listing(env, region, venue, soup, url)
    seen = set()
    for item in artlogic_items(soup, url):
        if city_marker and item['location'] and city_marker not in item['location'].lower():
            continue
        start, end = parse_day_first_range(item['date_text'])
        if start or end:
            listing.add(item['name'], start, end, link=item['link'], tag='gallery', seen=seen)
    if not listing.publish():
        logging.warning(f"{venue}: no exhibitions found; existing data kept.")
