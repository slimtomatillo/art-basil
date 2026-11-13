"""The Bronx Museum of the Arts, 1040 Grand Concourse: the exhibitions on its current and upcoming listings.

bronxmuseum.org/exhibitions/ has date filters (?date_filter=current, ?date_filter=upcoming). Each links to the shows' pages
(/exhibition/<slug>), from which the dates, title and description are read (scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'The Bronx Museum of the Arts'
LISTINGS = ['https://bronxmuseum.org/exhibitions/?date_filter=current', 'https://bronxmuseum.org/exhibitions/?date_filter=upcoming']
SHOW_PATTERN = r'^/exhibition/[a-z0-9-]+/?$'
TITLE_SUFFIX = ' - The Bronx Museum'


def scrape_bronx_museum_of_the_arts(env='prod', region='nyc'):
    """Scrape and process The Bronx Museum of the Arts's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
