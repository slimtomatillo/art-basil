from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, join_name
from processing import region_today
import logging

URLS = ['https://www.davidkordanskygallery.com/exhibitions', 'https://www.davidkordanskygallery.com/exhibitions/upcoming']
VENUE = 'David Kordansky Gallery'
# Each show is "Artist | Title | dates | place"; the gallery also shows in New York and Santa Barbara
PLACES = ('Los Angeles', 'New York', 'Santa Barbara')
STOPS = ('Current', 'Upcoming', 'Past', 'Book a Tour') + PLACES


def scrape_david_kordansky_gallery(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at David Kordansky Gallery's Los Angeles space."""
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
        for parts, start, end, i in dated_headings(lines, today, stops=STOPS, after=1):
            if parts and i + 1 < len(lines) and lines[i + 1] == 'Los Angeles':
                listing.add(join_name(parts), start, end, anchor=parts[0], seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("David Kordansky Gallery: could not fetch the exhibitions pages; existing data kept.")
    elif not stored:
        logging.warning("David Kordansky Gallery: no Los Angeles exhibitions found; existing data kept.")
