"""The Frick Collection, 1 East 70th St: the exhibitions on its listing page.

https://www.frick.org/exhibitions has three sections, Current, Upcoming and Past (past is not read). Each show is a
block (.paragraph-card__body-text) with a first paragraph holding the title and, after a line break, the run
("October 15, 2026 to January 18, 2027"), then a paragraph of description and a "Read More" link to the show's page.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.frick.org/exhibitions'
VENUE = 'The Frick Collection'
_MAX_DESCRIPTION = 400


def scrape_frick_collection(env='prod', region='nyc'):
    """Scrape and process the Frick's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Frick Collection: could not fetch the exhibitions page; existing data kept.")
        return
    # The page's sections are headed Current, Upcoming and Past (the same words are also in a menu above them, whose
    # entries have no show cards after them); the shows after the last "Past" heading are past ones
    past = set()
    headings = [tag for tag in soup.find_all(['h2', 'h3']) if clean(tag.get_text(' ')).lower() == 'past']
    if headings:
        past = {id(body) for body in headings[-1].find_all_next(class_='paragraph-card__body-text')}
    found = 0
    seen = set()
    for body in soup.select('.paragraph-card__body-text'):
        if id(body) in past:
            continue
        paragraphs = body.find_all('p')
        if len(paragraphs) < 2:
            continue
        head = [clean(t) for t in paragraphs[0].stripped_strings]
        if len(head) < 2:
            continue
        name, run = head[0], head[-1]
        start_date, end_date = parse_dates(run, today)
        link = body.find('a', href=True)
        if not (start_date or end_date) or link is None:
            continue
        description = clean(paragraphs[1].get_text(' ')) if len(paragraphs) > 2 else None
        if description and len(description) > _MAX_DESCRIPTION:
            description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
        card = body.find_parent(class_='paragraph-card') or body.parent
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, link['href']), tag='museum',
                         description=description, seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Frick Collection: no current or upcoming exhibition found; existing data kept.")
