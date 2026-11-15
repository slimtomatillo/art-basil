"""Asia Society Museum, 725 Park Ave: the exhibitions on its Current and Upcoming pages.

https://asiasociety.org/new-york/exhibitions/current and /new-york/exhibitions (Upcoming) answer GitHub's servers with
a Cloudflare challenge, so they are fetched through the ZenRows proxy (WEBSITE-121, tier 4). Each show is a card with a
picture, an h4 link to the show's page (the title), a run written day first ("18 Mar 2026 - 03 Jan 2027") and a short
description.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGES = ['https://asiasociety.org/new-york/exhibitions/current', 'https://asiasociety.org/new-york/exhibitions']
VENUE = 'Asia Society Museum'
_MAX_DESCRIPTION = 400
_RUN = re.compile(r'\d{1,2} [A-Za-z]{3,9} \d{4}\s*[-–—]\s*\d{1,2} [A-Za-z]{3,9} \d{4}')


def _card(heading):
    """The element around a title that also holds its picture and dates."""
    element = heading
    for _ in range(5):
        element = element.parent
        if element is None:
            return None
        if element.find('img') and len(element.find_all('h4')) == 1:
            return element
    return None


def scrape_asia_society_museum(env='prod', region='nyc'):
    """Scrape and process Asia Society Museum's current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    for page_url in PAGES:
        soup = fetch_and_parse(page_url)
        if soup is None:
            logging.warning(f"Asia Society Museum: could not fetch {page_url}; existing data kept.")
            continue
        for link in soup.select('h4 a[href*="/new-york/exhibitions/"]'):
            card = _card(link.find_parent('h4'))
            if card is None:
                continue
            name = clean(link.get_text(' '))
            lines = [clean(line) for line in card.get_text('\n').split('\n') if clean(line)]
            # the run is split over two lines ("18 Mar 2026" / "- 03 Jan 2027"), so it is read from the card's whole text
            run = _RUN.search(clean(card.get_text(' ')))
            start_date, end_date = parse_dates(run.group(0), today) if run else (None, None)
            if not (name and (start_date or end_date)):
                continue
            description = next((line for line in lines if len(line) > 60 and line != name), None)
            if description and len(description) > _MAX_DESCRIPTION:
                description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
            found += publish(env, region, VENUE, name, start_date, end_date, urljoin(page_url, link['href']), tag='museum',
                             description=description, seen=seen, image=card_picture(card, page_url))
    if not found:
        logging.warning("Asia Society Museum: no current or upcoming exhibition found; existing data kept.")
