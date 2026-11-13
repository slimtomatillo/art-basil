"""American Folk Art Museum, 2 Lincoln Square: the exhibitions on its Current and Upcoming pages.

folkartmuseum.org/exhibitions/ has a page for each (/exhibitions/current/ and /exhibitions/upcoming/), each linking to
the shows' pages (/exhibitions/<slug>); the title, dates ("October 9, 2026–February 28, 2027") and description are
read from each page (scrapers/nyc/_pages.py). Its pages carry no share tags, so the title is the page's <title>.
"""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'American Folk Art Museum'
LISTINGS = ['https://folkartmuseum.org/exhibitions/current/', 'https://folkartmuseum.org/exhibitions/upcoming/']
SHOW_PATTERN = r'^/exhibitions/[a-z0-9-]+/?$'
TITLE_SUFFIX = ' | American Folk Art Museum'


def scrape_american_folk_art_museum(env='prod', region='nyc'):
    """Scrape and process the American Folk Art Museum's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
