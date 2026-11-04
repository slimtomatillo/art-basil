from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from date_parsing import parse_date_text
from processing import region_today
import logging

URLS = ['https://gagosian.com/exhibitions/', 'https://gagosian.com/exhibitions/upcoming/']
VENUE = 'Gagosian Beverly Hills'
CITY = 'Beverly Hills'


def scrape_gagosian_beverly_hills(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Gagosian's Beverly Hills gallery (its other cities are left out)."""
    today = region_today(region)
    seen = set()
    fetched = stored = 0
    for url in URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        fetched += 1
        lines = page_lines(soup)
        # Shows follow the last "List" view toggle, each as "Artist | Title | Curated by X | November 4 | – | December 19, 2026 | City"
        # (a short run is written "November 4 | – | 7, 2026")
        floor = max((i for i, l in enumerate(lines) if l == 'List'), default=-1) + 1
        listing = Listing(env, region, VENUE, soup, url)
        for j, line in enumerate(lines):
            if line != '–' or j - 1 < floor or j + 2 >= len(lines):
                continue
            heading = [l for l in lines[floor:j - 1] if not l.startswith('Curated by')]
            floor = j + 3
            if lines[j + 2] != CITY or not heading:
                continue
            start, end = parse_date_text(f"{lines[j - 1]} - {lines[j + 1]}", today)
            if start or end:
                name = f"{heading[0]}: {heading[1]}" if len(heading) > 1 else heading[0]
                listing.add(name, start, end, anchor=heading[0], seen=seen)
        stored += listing.publish()
    if not fetched:
        logging.warning("Gagosian Beverly Hills: could not fetch the exhibitions pages; existing data kept.")
    elif not stored:
        logging.warning("Gagosian Beverly Hills: no exhibitions found; existing data kept.")
