"""The Drawing Center, 35 Wooster St, SoHo: the exhibitions at drawingcenter.org/exhibitions.

The listing links to each show's page (/exhibitions/<slug>); the dates, title and description are read from that page
(scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'The Drawing Center'
LISTINGS = ['https://drawingcenter.org/exhibitions']
SHOW_PATTERN = r'^/exhibitions/[a-z0-9-]+/?$'
TITLE_SUFFIX = ' | The Drawing Center'


def scrape_drawing_center(env='prod', region='nyc'):
    """Scrape and process The Drawing Center's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
