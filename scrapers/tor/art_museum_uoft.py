from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import publish
from processing import region_today
import logging

BASE_URL = 'https://artmuseum.utoronto.ca'
VENUE = 'Art Museum at the University of Toronto'

# (page, CSS selector for its entries, kind of entry). The museum's own sidebar menu leads to
# these three pages; each entry is <div class="... item"><a href><h3 class="item-title">
# <p class="date">. "Upcoming Exhibitions" is on the exhibitions page and is empty between shows.
PAGES = (
    (BASE_URL + '/exhibitions/', '#current .exhibition.item, #upcoming .exhibition.item', 'exhibition'),
    (BASE_URL + '/exhibition-type/touring-exhibitions/', '.post.item.touring-exhibitions', 'exhibition'),
    (BASE_URL + '/programs/', '#current .program.item', 'event'),
)


def scrape_art_museum_uoft(env='prod', region='tor'):
    """Scrape and process the exhibitions, touring exhibitions and programs of the Art Museum at the
    University of Toronto (the Justina M. Barnicke Gallery and the University of Toronto Art Centre).
    Admission is free."""
    today = region_today(region)
    found = 0
    fetched = 0
    seen = set()
    for url, selector, kind in PAGES:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Art Museum at the University of Toronto: could not fetch {url}; existing data kept.")
            continue
        fetched += 1
        for item in soup.select(selector):
            title = item.select_one('.item-title')
            date = item.select_one('.date')
            link = item.select_one('a[href]')
            if not (title and date and link):
                continue
            # Dates read "September 26, 2026–December 20, 2026" (a <br> may follow the dash) or a single day
            start_date, end_date = parse_date_text(' '.join(date.get_text(' ').split()), today)
            if start_date and not end_date:
                end_date = start_date
            found += publish(env, region, VENUE, ' '.join(title.get_text().split()), start_date, end_date,
                             link['href'], tag='museum', kind=kind, extra_tags=('free',), seen=seen)
    if fetched and not found:
        logging.info("Art Museum at the University of Toronto: nothing current or upcoming on its pages.")
