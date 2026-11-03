from utils import fetch_and_parse
from scrapers.sf._artlogic import parse_day_first_range
from scrapers.tor._common import page_lines, publish
import logging

EXHIBITIONS_URL = 'https://thegoldfarbgallery.ca/exhibitions/'


def scrape_goldfarb_gallery(env='prod', region='tor'):
    """Scrape and process the exhibitions of The Joan and Martin Goldfarb Gallery of York University
    (formerly the Art Gallery of York University, AGYU)."""
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Goldfarb Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    seen = set()
    # Each entry: title (sometimes split over two lines, the first ending ":" or ",") /
    # "exhibition" or "on-site exhibition" / "11 Sep 2026 – 6 Mar 2027". The archive follows;
    # past shows are skipped when publishing.
    for i, line in enumerate(lines[:-1]):
        if 'exhibition' not in line.lower() or len(line) > 25 or i < 2:
            continue
        start_date, end_date = parse_day_first_range(lines[i + 1].replace('–', ' – '))
        if not (start_date and end_date):
            continue
        name = lines[i - 1]
        if lines[i - 2].endswith((':', ',')):
            name = f'{lines[i - 2]} {name}'
        found += publish(env, region, 'The Joan and Martin Goldfarb Gallery of York University', name,
                         start_date, end_date, EXHIBITIONS_URL, tag='gallery', seen=seen)
    if not found:
        logging.warning("Goldfarb Gallery: no exhibitions found; existing data kept.")
