from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, index_of, join_name
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.robertsprojectsla.com/exhibitions'
VENUE = 'Roberts Projects'


def scrape_roberts_projects(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Roberts Projects."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Roberts Projects: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    # "Upcoming" (and "Current") lists come first, then a "Past" list that runs back to 2000
    end = index_of(lines, 'Past', len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for parts, start, finish, _ in dated_headings(lines, today, end=end, stops=('Upcoming', 'Current', 'Exhibitions')):
        if parts:
            listing.add(join_name(parts), start, finish, anchor=parts[0])
    if not listing.publish():
        logging.warning("Roberts Projects: no exhibitions found; existing data kept.")
