from utils import fetch_and_parse
from scrapers.sf._artlogic import parse_day_first_range
from scrapers.tor._common import page_lines, publish
import logging

EXHIBITIONS_URL = 'https://www.mercerunion.org/exhibitions'


def scrape_mercer_union(env='prod', region='tor'):
    """Scrape and process the exhibition on view at Mercer Union."""
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Mercer Union: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    # "On View" / "26 September 2026—23 January 2027" / artist / title
    for i, line in enumerate(lines[:-3]):
        if line != 'On View':
            continue
        start_date, end_date = parse_day_first_range(lines[i + 1].replace('—', ' — '))
        found += publish(env, region, 'Mercer Union', f'{lines[i + 2]}: {lines[i + 3]}', start_date, end_date,
                         EXHIBITIONS_URL, tag='gallery')
    if not found:
        logging.warning("Mercer Union: no exhibition on view found; existing data kept.")
