from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, join_name
from processing import region_today
import logging

URLS = ['https://spruethmagers.com/exhibitions/', 'https://spruethmagers.com/exhibitions/upcoming/']
VENUE = 'Sprüth Magers Los Angeles'
STOPS = ('Explore now', 'Current Exhibitions', 'Upcoming Exhibitions', 'Past Exhibitions')


def scrape_spruth_magers_los_angeles(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Sprüth Magers' Los Angeles gallery (its other cities are left out)."""
    today = region_today(region)
    seen = set()
    fetched = stored = 0
    for url in URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        fetched += 1
        lines = page_lines(soup)
        listing = Listing(env, region, VENUE, soup, url)
        # "Artist | Title | September 11–December 12, 2026 | Los Angeles | a paragraph | Explore now"
        for parts, start, end, i in dated_headings(lines, today, stops=STOPS, after=1):
            if parts and i + 1 < len(lines) and lines[i + 1] == 'Los Angeles':
                listing.add(join_name(parts), start, end, anchor=parts[0], seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("Sprüth Magers Los Angeles: could not fetch the exhibitions pages; existing data kept.")
    elif not stored:
        logging.warning("Sprüth Magers Los Angeles: no exhibitions found; existing data kept.")
