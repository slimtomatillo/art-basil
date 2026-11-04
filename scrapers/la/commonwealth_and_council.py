from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import is_fair
from date_parsing import parse_date_text
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://commonwealthandcouncil.com/exhibitions'
VENUE = 'Commonwealth and Council'


def scrape_commonwealth_and_council(env='prod', region='la'):
    """Scrape and process the exhibitions at Commonwealth and Council (fair booths are left out)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Commonwealth and Council: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    # The list starts under a "2026" heading; each show is "Title | Artist | November 7, 2026 | – | December 19, 2026"
    floor = lines.index('2026') + 1 if '2026' in lines else 0
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for j, line in enumerate(lines):
        if line != '–' or j < floor + 1 or j + 1 >= len(lines):
            continue
        heading = lines[max(floor, j - 3):j - 1]
        floor = j + 2
        start, end = parse_date_text(f"{lines[j - 1]} - {lines[j + 1]}", today)
        if not heading or not (start or end):
            continue
        title, artist = heading[0], heading[1] if len(heading) > 1 else None
        if is_fair(title):
            continue
        listing.add(f"{artist}: {title}" if artist else title, start, end, anchor=title)
    if not listing.publish():
        logging.warning("Commonwealth and Council: no exhibitions found; existing data kept.")
