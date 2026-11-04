from utils import fetch_and_parse
from scrapers.tor._common import publish
from date_parsing import parse_date_text
from processing import region_today
from urllib.parse import urljoin
import logging

EXHIBITIONS_URL = 'https://galeriesimonblais.com/en/expos/'
VENUE = 'Galerie Simon Blais'


def scrape_galerie_simon_blais(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at Galerie Simon Blais."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Galerie Simon Blais: could not fetch the exhibitions page; existing data kept.")
        return
    # Each show is a row: <a><img></a> then .expo_summary_artists (h3), .expo_summary_name, .expo_summary_dates
    # ("Nov. 4, 2026 to Dec. 19, 2026") and a View button. The page lists the shows twice, and shows held
    # "OFFSITE - HORS-GALERIE" at a museum are not in the gallery.
    seen = set()
    stored = 0
    for text in soup.select('.expo_summary_text'):
        artist, title, dates, button = (text.select_one('.expo_summary_artists'), text.select_one('.expo_summary_name'),
                                        text.select_one('.expo_summary_dates'), text.select_one('a[href]'))
        if not (artist and title and dates):
            continue
        artist, title = artist.get_text(' ', strip=True), title.get_text(' ', strip=True)
        start, end = parse_date_text(dates.get_text(' ', strip=True), today)
        if 'OFFSITE' in title.upper() or not (start or end):
            continue
        row = text.find_parent(class_='row')
        img = row.select_one('img[src]') if row else None
        stored += publish(env, region, VENUE, f"{artist}: {title}", start, end,
                          urljoin(EXHIBITIONS_URL, button['href']) if button else EXHIBITIONS_URL, tag='gallery',
                          seen=seen, image=urljoin(EXHIBITIONS_URL, img['src']) if img else None)
    if not stored:
        logging.warning("Galerie Simon Blais: no exhibitions found; existing data kept.")
