from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging

PAGE_URL = 'https://dorismccarthygallery.utoronto.ca'
_LABELS = ('current exhibition', 'upcoming exhibition')


def scrape_doris_mccarthy_gallery(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at the Doris McCarthy Gallery (UTSC)."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Doris McCarthy Gallery: could not fetch the home page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Doris McCarthy Gallery', soup, PAGE_URL)
    seen = set()
    # "Current Exhibition" / "/" / "September 15 – December 5, 2026" / title / artists
    for i, line in enumerate(lines[:-3]):
        if line.lower() not in _LABELS:
            continue
        start_date, end_date = parse_date_text(lines[i + 2], today)
        listing.add(lines[i + 3], start_date, end_date, tag='gallery', seen=seen)
    found = listing.publish()
    if not found:
        logging.warning("Doris McCarthy Gallery: no exhibitions found; existing data kept.")
