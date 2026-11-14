"""The Studio Museum in Harlem, 144 W 125th St: the exhibitions on its listing page.

https://www.studiomuseum.org/exhibitions lists activity cards (links with schema.org/Event): a picture, the title
(twice, for the picture's text and the card's) and a line that is the run: "Through January 3, 2027", or
"02.11.27-05.16.27" (month.day.year to month.day.year) for shows not yet open. "Ongoing" and "On Long-term View" are
permanent installations and are left out. Each show's own page is linked; descriptions.py reads it.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, numeric_run, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.studiomuseum.org/exhibitions'
VENUE = 'The Studio Museum in Harlem'


def _dates(text, today):
    """(start, end) from "Through January 3, 2027" or "02.11.27-05.16.27"; (None, None) for anything else."""
    start, end = numeric_run(text)
    return (start, end) if (start or end) else parse_dates(text, today)


def scrape_studio_museum_in_harlem(env='prod', region='nyc'):
    """Scrape and process the Studio Museum's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Studio Museum in Harlem: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('a[href^="/exhibitions/"]'):
        lines = [clean(t) for t in card.stripped_strings]
        lines = [line for line in lines if line]
        if len(lines) < 2:
            continue
        name, text = lines[0], lines[-1]
        start_date, end_date = _dates(text, today)
        if not (start_date or end_date):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']),
                         tag='museum', seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Studio Museum in Harlem: no current or upcoming exhibition found; existing data kept.")
