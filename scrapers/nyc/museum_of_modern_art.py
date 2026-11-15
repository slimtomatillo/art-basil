"""The Museum of Modern Art, 11 W 53rd St: the exhibitions on its listing page.

https://www.moma.org/calendar/exhibitions answers GitHub's servers with a Cloudflare challenge, so it is fetched through
the ZenRows proxy (WEBSITE-121, tier 4). Under "Current exhibitions", "Upcoming exhibitions" and "Installations and
projects" each show is a link to /calendar/exhibitions/<number> holding a picture, an h3 with the title (the first
paragraph is the whole title) and a last paragraph with the dates ("Through Nov 29", "Nov 21, 2026–Feb 7, 2027").
A display marked "Ongoing" is left out.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.moma.org/calendar/exhibitions'
VENUE = 'Museum of Modern Art'


def scrape_museum_of_modern_art(env='prod', region='nyc'):
    """Scrape and process MoMA's current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("MoMA: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.find_all('a', href=re.compile(r'^/calendar/exhibitions/\d+')):
        heading = card.find('h3')
        paragraphs = [clean(p.get_text(' ')) for p in card.find_all('p') if heading not in p.parents]
        first = heading.find('p') if heading else None
        if first is None or not paragraphs:
            continue
        dates = paragraphs[-1]
        if 'ongoing' in dates.lower():
            continue
        start_date, end_date = parse_dates(dates, today)
        name = clean(first.get_text(' '))
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, urljoin(PAGE_URL, card['href']), tag='museum',
                         seen=seen, image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("MoMA: no current or upcoming exhibition found; existing data kept.")
