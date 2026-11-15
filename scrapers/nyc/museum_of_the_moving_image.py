"""Museum of the Moving Image, 36-01 35th Ave, Queens: the exhibitions on its listing page.

https://movingimage.org/whats-on/exhibitions/ answers GitHub's servers with a Cloudflare challenge, so it is fetched
through the ZenRows proxy (WEBSITE-121, tier 4). Under the h2 "Current exhibitions" (up to the h2 "Exhibition archive")
each show is a block with a picture, an h2 (the title), a paragraph with the run ("October 10, 2026–March 21, 2027")
and a paragraph of description. The blocks do not link to a page of their own, so each links to the listing. A show
with no run (the permanent Jim Henson Exhibition) is left out.
"""
import logging

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://movingimage.org/whats-on/exhibitions/'
VENUE = 'Museum of the Moving Image'
_MAX_DESCRIPTION = 400


def scrape_museum_of_the_moving_image(env='prod', region='nyc'):
    """Scrape and process the Museum of the Moving Image's current exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Museum of the Moving Image: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    inside = False
    for heading in soup.find_all('h2'):
        title = clean(heading.get_text(' '))
        if title.lower() == 'current exhibitions':
            inside = True
            continue
        if title.lower() == 'exhibition archive':
            break
        if not inside:
            continue
        paragraphs = [clean(p.get_text(' ')) for p in heading.parent.find_all('p')]
        if not paragraphs:
            continue
        start_date, end_date = parse_dates(paragraphs[0], today)
        if not (title and (start_date or end_date)):
            continue
        description = paragraphs[1] if len(paragraphs) > 1 else None
        if description and len(description) > _MAX_DESCRIPTION:
            description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
        card = heading.parent.parent if heading.parent.parent and heading.parent.parent.find('img') else heading.parent
        found += publish(env, region, VENUE, title, start_date, end_date, PAGE_URL, tag='museum',
                         description=description, seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("Museum of the Moving Image: no current exhibition found; existing data kept.")
