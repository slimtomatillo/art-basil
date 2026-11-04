from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import index_of
from date_parsing import parse_date_text
from processing import region_today
import logging
import re

LISTING_URL = 'https://www.oboro.net/programmation/'
VENUE = 'OBORO'
_YEAR_RE = re.compile(r'\b\d{4}$')
# Under the "Expositions" heading each show is "2 oct | au | 28 nov 2026 | Title | Exposition collective | Commissaire : ..."
# or, for a solo show, "20 | au | 28 nov 2026 | Artist | Title"
_TYPE_PREFIXES = ('Exposition', 'Commissaire', 'Installation', 'Projection')


def scrape_oboro(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at OBORO."""
    today = region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("OBORO: could not fetch the programme page; existing data kept.")
        return
    lines = page_lines(soup)
    begin = index_of(lines, 'Expositions')
    end = next((i for i, l in enumerate(lines) if i > begin and l in ('Événements', 'Résidences', 'Activités')), len(lines))
    listing = Listing(env, region, VENUE, soup, LISTING_URL)
    for i in range(begin, end - 3):
        if lines[i + 1] != 'au' or not _YEAR_RE.search(lines[i + 2]):
            continue
        start, finish = parse_date_text(f"{lines[i]} au {lines[i + 2]}", today)
        first, second = lines[i + 3], lines[i + 4] if i + 4 < end else ''
        name = first if not second or second.startswith(_TYPE_PREFIXES) else f"{first}: {second}"
        if start or finish:
            listing.add(name, start, finish, anchor=first, tag='gallery')
    if not listing.publish():
        logging.warning("OBORO: no exhibitions found; existing data kept.")
