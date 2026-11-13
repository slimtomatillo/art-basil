from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging
import re
from urllib.parse import urljoin

PAGE_URL = 'https://www.paulpetro.com/ppca/current'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')
_RECEPTION_RE = re.compile(r'^opening reception', re.IGNORECASE)


def scrape_paul_petro_contemporary_art(env='prod', region='tor'):
    """Scrape and process the current exhibitions at Paul Petro Contemporary Art."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Paul Petro: could not fetch the current page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, 'Paul Petro Contemporary Art', soup, PAGE_URL)
    # Each title links to the show's own page, which is the better Event Page link and the place
    # images.py finds the show's picture (the listing itself has only the gallery logo).
    show_pages = {re.sub(r'\W+', '', a.get_text().lower()): urljoin(PAGE_URL, a['href'])
                  for a in soup.select('h1 a[href]')}
    # Each show is: title / artist / subtitle / dates / opening reception. A show with no artist line (the
    # Christmas show: title / "tree by ..." / dates) has the previous show's reception line where its artist
    # would be, so that line is not read as part of it.
    # "Current Regional Programming" (art-fair booths) sits in the same list and is skipped.
    for i, line in enumerate(lines):
        if i < 3 or not _RANGE_RE.match(line) or 'regional programming' in lines[i - 1].lower():
            continue
        title, artist, subtitle = lines[i - 3:i]
        if _RECEPTION_RE.match(title):
            title, artist, subtitle = artist, None, subtitle
        start_date, end_date = parse_date_text(line, today)
        name = f'{title}: {artist} - {subtitle}' if artist else f'{title} - {subtitle}'
        listing.add(name, start_date, end_date, tag='gallery',
                    link=show_pages.get(re.sub(r'\W+', '', title.lower())))
    found = listing.publish()
    if not found:
        logging.warning("Paul Petro: no exhibitions found; existing data kept.")
