from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, join_name
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.regenprojects.com/exhibitions'
VENUE = 'Regen Projects'


def scrape_regen_projects(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Regen Projects."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Regen Projects: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # "Artist | Title | November 6 – December 19, 2026 | street address"; the Upcoming/Past tabs come first
    for parts, start, end, _ in dated_headings(lines, today, stops=('Upcoming', 'Past', 'Exhibitions'), after=1):
        if parts:
            listing.add(join_name(parts), start, end, anchor=parts[0])
    if not listing.publish():
        logging.warning("Regen Projects: no exhibitions found; existing data kept.")
