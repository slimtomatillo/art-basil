"""Neue Galerie New York, 1048 Fifth Ave: the exhibitions at neuegalerie.org/exhibitions.

The listing links to each show's page (/exhibitions/<slug>); the dates, title and description are read from that page
(scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'Neue Galerie New York'
LISTINGS = ['https://www.neuegalerie.org/exhibitions']
SHOW_PATTERN = r'^/exhibitions/[a-z0-9-]+/?$'
TITLE_SUFFIX = ''


def scrape_neue_galerie_new_york(env='prod', region='nyc'):
    """Scrape and process Neue Galerie New York's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
