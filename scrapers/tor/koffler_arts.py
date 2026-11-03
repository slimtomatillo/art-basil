from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.kofflerarts.org/whatson/exhibitions'


def scrape_koffler_arts(env='prod', region='tor'):
    """Scrape and process the gallery exhibitions of Koffler Arts."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Koffler Arts: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    # Each show reads: "Gallery Exhibitions" / dates / title / artist / location
    for i, line in enumerate(lines[:-2]):
        if line != 'Gallery Exhibitions':
            continue
        start_date, end_date = parse_date_text(lines[i + 1], today)
        # The title line already carries the artist ("Kamiphony | Cybèle Young")
        found += publish(env, region, 'Koffler Arts', lines[i + 2].replace(' | ', ': '), start_date, end_date,
                         EXHIBITIONS_URL, tag='gallery')
    if not found:
        logging.warning("Koffler Arts: no exhibitions found; existing data kept.")
