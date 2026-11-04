from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://fisher.usc.edu/whats-on-view/'
VENUE = 'USC Fisher Museum of Art'
# The page leads with the show on view: "Now open" / title / "Aug. 18, 2026-March 13, 2027".
# The past exhibitions and the "related exhibitions at Getty and LACMA" lower down are other
# entries with their own dates and are not read.
_LABELS = ('now open', 'opening soon', 'coming soon', 'upcoming')


def scrape_usc_fisher_museum_of_art(env='prod', region='la'):
    """Scrape and process the exhibition(s) at the USC Fisher Museum of Art."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("USC Fisher Museum of Art: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines[:-2]):
        if line.lower() in _LABELS:
            start_date, end_date = parse_date_text(lines[i + 2], today)
            listing.add(lines[i + 1], start_date, end_date, tag='museum')
    if not listing.publish():
        logging.warning("USC Fisher Museum of Art: no exhibitions found; existing data kept.")
