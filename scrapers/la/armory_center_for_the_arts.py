from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging

CURRENT_URL = 'https://www.armoryarts.org/exhibitions/current'
VENUE = 'Armory Center for the Arts'


def scrape_armory_center_for_the_arts(env='prod', region='la'):
    """Scrape and process the current exhibitions at the Armory Center for the Arts (always free)."""
    today = region_today(region)
    soup = fetch_and_parse(CURRENT_URL)
    if soup is None:
        logging.warning("Armory Center for the Arts: could not fetch the current exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, CURRENT_URL)
    # "Now on view through" / "Jan 16, 2027" / title
    for i, line in enumerate(lines[:-2]):
        if line.lower() == 'now on view through':
            start_date, end_date = parse_date_text(f'Through {lines[i + 1]}', today)
            listing.add(lines[i + 2], start_date, end_date, tag='gallery', extra_tags=('free',))
    if not listing.publish():
        logging.warning("Armory Center for the Arts: no current exhibitions found; existing data kept.")
