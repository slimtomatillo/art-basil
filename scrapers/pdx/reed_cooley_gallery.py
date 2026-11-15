"""Reed College's Cooley Gallery (Douglas F. Cooley Memorial Art Gallery), 3203 SE Woodstock Blvd: its exhibitions page links to
a page per show (/cooley/exhibitions/<slug>.html, past ones included; ended shows are dropped); the dates, title and
description are read from that page (scrapers/nyc/_pages.py)."""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'Cooley Gallery'
LISTINGS = ['https://www.reed.edu/cooley/exhibitions/index.html']
SHOW_PATTERN = r'/cooley/exhibitions/[a-z0-9-]+\.html'
TITLE_SUFFIX = ' - Cooley Gallery - Reed College'


def scrape_cooley_gallery(env='prod', region='pdx'):
    """Scrape and process the Cooley Gallery's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX, tag='gallery')
