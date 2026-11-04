from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://www.janm.org/exhibitions'
VENUE = 'Japanese American National Museum'
# Each entry is a type line, the dates, then the title: "Upcoming Exhibition" / "Jan 23 - Aug 29, 2027" /
# "Pictures of Belonging ...". Entries of those types with no dates say "Ongoing". "Traveling Display"
# is shown at other places and "Past Exhibition" is the archive.
_TYPES = ('upcoming exhibition', 'special display', 'exhibition')


def scrape_japanese_american_national_museum(env='prod', region='la'):
    """Scrape and process the exhibitions of the Japanese American National Museum (closed for
    renovation until January 2027, so most entries are upcoming)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Japanese American National Museum: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i, line in enumerate(lines[:-2]):
        if line.lower() in _TYPES and lines[i + 1].lower() != 'ongoing':
            start_date, end_date = parse_date_text(lines[i + 1], today)
            if start_date and end_date:
                listing.add(lines[i + 2], start_date, end_date, tag='museum')
    if not listing.publish():
        logging.warning("Japanese American National Museum: no current or upcoming exhibitions found; existing data kept.")
