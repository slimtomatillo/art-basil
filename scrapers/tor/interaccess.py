from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.interaccess.org/exhibitions'
_LABELS = ('upcoming exhibition', 'current exhibition')


def scrape_interaccess(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at InterAccess."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("InterAccess: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    # "Upcoming exhibition" / "Nov 4" / "-" / "Dec 5, 2026" / title; the archive is labelled "PAST EXHIBITION"
    for i, line in enumerate(lines[:-4]):
        if line.lower() not in _LABELS:
            continue
        start_date, end_date = parse_date_text(f'{lines[i + 1]} - {lines[i + 3]}', today)
        found += publish(env, region, 'InterAccess', lines[i + 4], start_date, end_date, EXHIBITIONS_URL, tag='gallery')
    if not found:
        logging.warning("InterAccess: no current or upcoming exhibitions found; existing data kept.")
