"""Cooper Hewitt, Smithsonian Design Museum, 2 E 91st St: the exhibitions on its Current and Upcoming pages.

cooperhewitt.org/exhibitions/ (current) and /exhibitions/upcoming/ list each show as a heading (the title in one span
and the run in the next: "On view THROUGH FEBRUARY 15, 2027", or "ONGOING" for a permanent display, which is left out)
followed by a block with the show's picture, a link to its page and a first paragraph of description.
"""
import logging
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates, title_case
from scrapers.tor._common import publish
from utils import fetch_and_parse

LISTINGS = ['https://www.cooperhewitt.org/exhibitions/', 'https://www.cooperhewitt.org/exhibitions/upcoming/']
VENUE = 'Cooper Hewitt'
_MAX_DESCRIPTION = 400


def scrape_cooper_hewitt(env='prod', region='nyc'):
    """Scrape and process Cooper Hewitt's current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    for page_url in LISTINGS:
        soup = fetch_and_parse(page_url)
        if soup is None:
            logging.warning(f"Cooper Hewitt: could not fetch {page_url}; existing data kept.")
            continue
        for row in soup.select('.post-row'):
            heading = row.find_previous_sibling('h2')
            link = row.find('a', href=True)
            if heading is None or link is None:
                continue
            spans = [clean(s.get_text(' ')) for s in heading.find_all('span')]
            if len(spans) < 2:
                continue
            name = title_case(spans[0]) if spans[0].isupper() else spans[0]
            start_date, end_date = parse_dates(spans[1], today)
            if not (start_date or end_date):
                continue                                        # "ONGOING": a permanent display
            paragraph = row.find('p')
            description = clean(paragraph.get_text(' ')) if paragraph else None
            if description and len(description) > _MAX_DESCRIPTION:
                description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
            found += publish(env, region, VENUE, name, start_date, end_date, urljoin(page_url, link['href']), tag='museum',
                             description=description or None, seen=seen, image=card_picture(row, page_url))
    if not found:
        logging.warning("Cooper Hewitt: no current or upcoming exhibition found; existing data kept.")
