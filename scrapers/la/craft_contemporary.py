from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

BASE_URL = 'https://www.craftcontemporary.org'
VENUE = 'Craft Contemporary'
# The listing pages carry no dates, so each show's own page is read: its title, then a line like
# "November 15, 2026 — May 2, 2027".
LISTINGS = (BASE_URL + '/', BASE_URL + '/upcoming-exhibitions/')
_SHOW_URL_RE = re.compile(r'^https://www\.craftcontemporary\.org/exhibitions/[^/?#]+/$')
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}, \d{4} [—–-] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_craft_contemporary(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Craft Contemporary."""
    today = region_today(region)
    urls = []
    for listing_url in LISTINGS:
        soup = fetch_and_parse(listing_url)
        if soup is None:
            logging.warning(f"Craft Contemporary: could not fetch {listing_url}; existing data kept.")
            continue
        for a in soup.find_all('a', href=True):
            if _SHOW_URL_RE.match(a['href']) and a['href'] not in urls:
                urls.append(a['href'])

    found = 0
    seen = set()
    for url in urls:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        lines = page_lines(soup)
        i = next((k for k, l in enumerate(lines) if k and _RANGE_RE.match(l)), None)
        if i is None:
            logging.warning(f"Craft Contemporary: no date range on {url}")
            continue
        start_date, end_date = parse_date_text(lines[i].replace('—', '-'), today)
        found += publish(env, region, VENUE, lines[i - 1], start_date, end_date, url, tag='museum', seen=seen)
    if not found:
        logging.warning("Craft Contemporary: no exhibitions found; existing data kept.")
