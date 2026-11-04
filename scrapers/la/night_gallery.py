from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, join_name, next_year_if_past
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.nightgallery.ca/exhibitions'
VENUE = 'Night Gallery'


def _case(text):
    """The site prints artist names and dates in capitals ("TIDAWHITNEY LEK")."""
    return text.title() if text.isupper() else text


def scrape_night_gallery(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Night Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Night Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # "ARTIST | Title | NOVEMBER 21 - JANUARY 30, 2026" (the page lists only current and upcoming
    # shows, and its New Year-crossing dates are written a year behind)
    for parts, start, end, _ in dated_headings(lines, today, stops=('Upcoming', 'Past', 'Exhibitions')):
        if parts:
            start, end = next_year_if_past(start, end, today)
            listing.add(join_name([_case(p) for p in parts]), start, end, anchor=parts[0])
    if not listing.publish():
        logging.warning("Night Gallery: no exhibitions found; existing data kept.")
