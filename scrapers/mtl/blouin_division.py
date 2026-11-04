from utils import fetch_and_parse
from scrapers.tor._common import Listing
from date_parsing import parse_date_text
from processing import region_today
from urllib.parse import urljoin
import logging

EXHIBITIONS_URL = 'https://blouin-division.com/en/exhibitions/'
VENUE = 'Blouin Division'


def scrape_blouin_division(env='prod', region='mtl'):
    """Scrape and process the exhibitions at Blouin Division's Montreal gallery (its Toronto ones are left out)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Blouin Division: could not fetch the exhibitions page; existing data kept.")
        return
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # Each item: <h2>2026 | Artist | MONTRÉAL</h2> <span class="subtitle">Title</span> <span class="date">Sep 10 - Nov 7, 2026</span>
    for li in soup.select('li'):
        heading, title, date, link = (li.select_one('.content h2'), li.select_one('.content .subtitle'),
                                      li.select_one('.content .date'), li.select_one('a[href]'))
        if not (heading and date and link):
            continue
        parts = [p.strip() for p in heading.get_text(' ', strip=True).split('|')]
        if len(parts) < 3 or 'MONTR' not in parts[-1].upper():
            continue
        start, end = parse_date_text(date.get_text(' ', strip=True), today)
        if not (start or end):
            continue
        artist = parts[1]
        name = f"{artist}: {title.get_text(' ', strip=True)}" if title else artist
        listing.add(name, start, end, link=urljoin(EXHIBITIONS_URL, link['href']), anchor=artist, tag='gallery')
    if not listing.publish():
        logging.warning("Blouin Division: no Montreal exhibitions found; existing data kept.")
