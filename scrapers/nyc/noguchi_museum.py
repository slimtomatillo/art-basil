"""The Noguchi Museum, Long Island City, Queens: the exhibitions at noguchi.org/museum/exhibitions/current/.

The listing links to each show's page (/museum/exhibitions/view/<slug>); the dates, title and description are read
from that page (scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'The Noguchi Museum'
LISTINGS = ['https://www.noguchi.org/museum/exhibitions/current/']
SHOW_PATTERN = r'/museum/exhibitions/view/[a-z0-9-]+'
TITLE_SUFFIX = ' - The Noguchi Museum'


def scrape_noguchi_museum(env='prod', region='nyc'):
    """Scrape and process The Noguchi Museum's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
