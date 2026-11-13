"""Museum of the City of New York, 1220 Fifth Ave: the exhibitions at mcny.org/exhibitions.

The listing links to each show's page (/exhibition/<slug>), including ended ones and online exhibitions; the dates, title
and description are read from each page and only current and upcoming shows are kept (scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'Museum of the City of New York'
LISTINGS = ['https://www.mcny.org/exhibitions']
SHOW_PATTERN = r'^/exhibition/[a-z0-9-]+/?$'
TITLE_SUFFIX = ''


def scrape_museum_of_the_city_of_new_york(env='prod', region='nyc'):
    """Scrape and process Museum of the City of New York's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
