"""MoMA PS1, 22-25 Jackson Ave, Queens: the exhibitions among its current and upcoming programs.

https://www.momaps1.org/en/programs?timeframe=current (and timeframe=upcoming) list programs of every kind as rows
(a.program-row) with a title, a line of dates ("Ends Mar 15, 2027", "Mar 20–Aug 8, 2027", or "Now On View" and
"Ongoing" for standing ones) and badges ("Exhibition", "On View", "Event"...). Only rows badged Exhibition or On View
are kept, and those with no readable date (just "Now On View" or "Ongoing") are left out.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import card_picture, clean, parse_dates, title_case
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGES = ['https://www.momaps1.org/en/programs?timeframe=current', 'https://www.momaps1.org/en/programs?timeframe=upcoming']
VENUE = 'MoMA PS1'


def scrape_moma_ps1(env='prod', region='nyc'):
    """Scrape and process MoMA PS1's current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    for page_url in PAGES:
        soup = fetch_and_parse(page_url)
        if soup is None:
            logging.warning(f"MoMA PS1: could not fetch {page_url}; existing data kept.")
            continue
        for row in soup.select('a.program-row[href]'):
            badges = [clean(b.get_text(' ')).lower() for b in row.select('.badge-list li')]
            if not any(b in ('exhibition', 'on view') for b in badges):
                continue
            title = row.select_one('.primary-heading__title')
            date = row.select_one('.primary-heading__date')
            if title is None or date is None:
                continue
            name = clean(title.get_text(' '))
            name = title_case(name) if name.isupper() else name
            text = re.sub(r'^ends\s+', 'Through ', clean(date.get_text(' ')), flags=re.IGNORECASE)
            start_date, end_date = parse_dates(text, today)
            if not (name and (start_date or end_date)):
                continue
            found += publish(env, region, VENUE, name, start_date, end_date, urljoin(page_url, row['href']), tag='museum',
                             seen=seen, image=card_picture(row, page_url))
    if not found:
        logging.warning("MoMA PS1: no current or upcoming exhibition found; existing data kept.")
