"""International Center of Photography (ICP), 84 Ludlow St, Lower East Side: the exhibitions at icp.org/exhibitions.

The listing links to each show's page (/exhibitions/<slug>); the dates, title and description are read from that page
(scrapers/nyc/_pages.py). Its share picture is sometimes a malformed address, which is then left off."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'International Center of Photography'
LISTINGS = ['https://www.icp.org/exhibitions']
# the section pages (past, education, traveling, Mana) are links of the same shape
SHOW_PATTERN = r'^/exhibitions/(?!past-|education-|traveling-|mana-)[a-z0-9%.-]+/?$'
TITLE_SUFFIX = ''


def scrape_international_center_of_photography(env='prod', region='nyc'):
    """Scrape and process International Center of Photography's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX)
