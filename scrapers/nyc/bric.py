"""BRIC, 647 Fulton St, Downtown Brooklyn: the exhibitions at bricartsmedia.org/events/exhibitions/.

The listing links to each show's page (/exhibition/<slug>); the title, dates and description are read from that page
(scrapers/nyc/_pages.py). BRIC writes a run as "10.08.26 - 12.12.26" (month.day.year); a single numeric date on a page
("12.10.26") is a one-day event, which is left out.
"""
from processing import region_today
from scrapers.nyc._pages import scrape_show_pages
from utils import fetch_and_parse

VENUE = 'BRIC'
LISTINGS = ['https://bricartsmedia.org/events/exhibitions/']
SHOW_PATTERN = r'^/exhibition/[a-z0-9-]+/?$'
TITLE_SUFFIX = ''


def scrape_bric(env='prod', region='nyc'):
    """Scrape and process BRIC's current and upcoming exhibitions."""
    scrape_show_pages(env, region, VENUE, LISTINGS, SHOW_PATTERN, fetch=fetch_and_parse, today=region_today(region),
                      suffix=TITLE_SUFFIX, tag='gallery')    # BRIC House's gallery is free to enter, like the other galleries
