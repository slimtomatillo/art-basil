from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
import logging

URLS = ['https://circa-art.com/exhibitions_period/en-cours/', 'https://circa-art.com/exhibitions_period/a-venir/']
VENUE = 'CIRCA art actuel'
STOPS = ('Passées', 'Années', 'Rechercher', 'Soutenir CIRCA')


def scrape_circa(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at CIRCA art actuel."""
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
        # "Title | Artist | Du 5 novembre au 19 décembre 2026", each show listed twice
        for parts, start, end, _ in dated_headings(lines, today, stops=STOPS):
            if parts:
                name = f"{parts[1]}: {parts[0]}" if len(parts) == 2 else parts[0]
                listing.add(name, start, end, anchor=parts[0], tag='gallery', seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("CIRCA art actuel: could not fetch the exhibitions pages; existing data kept.")
    elif not stored:
        logging.info("CIRCA art actuel: no current or upcoming exhibitions.")
