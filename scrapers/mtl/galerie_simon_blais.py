from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://galeriesimonblais.com/en/expos/'
VENUE = 'Galerie Simon Blais'


def scrape_galerie_simon_blais(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at Galerie Simon Blais."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Galerie Simon Blais: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # "Jean McEwen | La lumière sous les blasons | Nov. 4, 2026 to Dec. 19, 2026 | View" (the page lists the shows twice,
    # and shows held "OFFSITE - HORS-GALERIE" at a museum are not in the gallery)
    seen = set()
    for parts, start, end, _ in dated_headings(lines, today, stops=('View',), after=1):
        if parts and not any('OFFSITE' in p.upper() for p in parts):
            listing.add(f"{parts[0]}: {parts[1]}" if len(parts) == 2 else parts[0], start, end, anchor=parts[0],
                        tag='gallery', seen=seen)
    if not listing.publish():
        logging.warning("Galerie Simon Blais: no exhibitions found; existing data kept.")
