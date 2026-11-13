"""Museum of Arts and Design (MAD), 2 Columbus Circle: the exhibitions at madmuseum.org/exhibitions.

The listing links to each show's page (/exhibition/<slug>), including ones that have ended and permanent displays
("Ongoing"); the dates, title and description are read from each page and only current and upcoming shows are kept
(scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'Museum of Arts and Design'
LISTINGS = ['https://madmuseum.org/exhibitions']
SHOW_PATTERN = r'^/exhibition/[a-z0-9-]+/?$'
TITLE_SUFFIX = ''


def scrape_museum_of_arts_and_design(env='prod', region='nyc'):
    """Scrape and process Museum of Arts and Design's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
