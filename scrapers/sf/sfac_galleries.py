"""SFAC Galleries (San Francisco Arts Commission): the exhibitions on https://www.sf.gov/sfac-galleries/.

(The gallery's old site, sfacgallery.org, no longer works as one - it ends up on an unrelated
domain - so do not use it.) The page lists the current and upcoming shows in columns: a picture,
then a <section> holding the space's name ("Main Gallery", "City Hall", "Cafe Valor"), the show's
title as an h3 link and its dates ("October 8, 2026 - January 30, 2027"). Artist talks and
workshops sit lower on the page under other headings and are not exhibitions, so only sections
named for one of the three spaces are read. The three spaces are two addresses (the Main Gallery
and Cafe Valor are both in the War Memorial Veterans Building) and are shown as one venue.
"""
import logging
from urllib.parse import urljoin

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.sf.gov/sfac-galleries/'
VENUE = 'SFAC Galleries'
SPACES = ('Main Gallery', 'City Hall', 'Cafe Valor')


def scrape_sfac_galleries(env='prod', region='sf'):
    """Scrape and process the exhibitions listed on the SFAC Galleries page."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("SFAC Galleries: could not fetch the galleries page; existing data kept.")
        return
    found = 0
    seen = set()
    for section in soup.find_all('section'):
        space = section.find('p')
        title_tag = section.find('h3')
        link = title_tag.find('a') if title_tag else None
        if space is None or link is None or space.get_text(' ', strip=True) not in SPACES:
            continue
        name = ' '.join(link.get_text(' ').split())
        date_tag = title_tag.find_next_sibling('p')
        start_date, end_date = parse_date_text(date_tag.get_text(' ') if date_tag else '', today)
        if not (start_date or end_date):
            logging.warning(f"SFAC Galleries: no readable dates for {name!r}")
            continue
        picture = section.parent.find('img') if section.parent else None
        image = picture.get('src') if picture else None
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link.get('href', '')),
                         tag='gallery', seen=seen, image=image)
    if not found:
        # Say what came back, so an empty result can be told from a block page or a changed layout
        title = soup.title.get_text(' ', strip=True)[:80] if soup.title else None
        logging.warning("SFAC Galleries: no current or upcoming exhibition found; existing data kept "
                        f"(page title {title!r}, {len(soup.find_all('section'))} sections, {len(str(soup))} bytes).")
