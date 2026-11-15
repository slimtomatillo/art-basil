"""Hauser & Wirth New York: the shows at its three New York spaces.

https://www.hauserwirth.com/hauser-wirth-exhibitions/ answers GitHub's servers with a Vercel challenge, so it is fetched
through the ZenRows proxy (WEBSITE-121, tier 4). The cards are built in the browser, but the page carries its data in a
`__NEXT_DATA__` script: pageProps.initialExhibitionsData.galleryExhibitionCollection.items lists the shows of every
city, each with a title ("Mike Kelley. Jerry Meandering"), a slug, start and end dates, the locations it is at
("New York, 18th Street") and a listing picture. Only shows at a New York location are kept, each stored with the space
it is at. (WEBSITE-64 keeps the Los Angeles shows hand-entered; this reads only New York.)
"""
import datetime as dt
import json
import logging
import re

from processing import region_today
from scrapers.nyc._common import clean
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.hauserwirth.com/hauser-wirth-exhibitions/'
SHOW_URL = 'https://www.hauserwirth.com/hauser-wirth-exhibitions/'
VENUE = 'Hauser & Wirth'
# The site's location name -> the label of the space in docs/data/nyc_venues.json
SPACES = {'18th Street': '18th Street', '22nd Street': '22nd Street', 'Wooster Street': 'Wooster Street'}


def _items(soup):
    """The exhibitions in the page's data, or []."""
    script = soup.find('script', id='__NEXT_DATA__')
    try:
        data = json.loads(script.string or script.get_text())
        return data['props']['pageProps']['initialExhibitionsData']['galleryExhibitionCollection']['items'] or []
    except (AttributeError, KeyError, TypeError, ValueError):
        return []


def _day(text):
    try:
        return dt.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _name(title):
    """"Mike Kelley. Jerry Meandering" -> "Mike Kelley: Jerry Meandering" (the site's separator for artist and title)."""
    return re.sub(r'(?<=\w)\.\s+(?=\S)', ': ', clean(title), count=1)


def _picture(item):
    images = item.get('listingPageImage') or item.get('thumbnailImage') or []
    if isinstance(images, dict):
        images = [images]
    for image in images:
        src = image.get('src') if isinstance(image, dict) else None
        if src and src.startswith('https://'):
            return src
    return None


def scrape_hauser_and_wirth(env='prod', region='nyc'):
    """Scrape and process Hauser & Wirth's New York exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Hauser & Wirth: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for item in _items(soup):
        places = [clean(place.get('name')) for place in (item.get('relatedLocationsCollection') or {}).get('items') or []]
        places = [p for p in places if p.lower().startswith('new york')]
        if not places or not item.get('slug'):
            continue
        spaces = [SPACES[p.split(',', 1)[-1].strip()] for p in places if p.split(',', 1)[-1].strip() in SPACES]
        start_date, end_date = _day(item.get('startDate')), _day(item.get('endDate'))
        name = _name(item.get('title') or '')
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, f"{SHOW_URL}{item['slug']}/", tag='gallery',
                         seen=seen, image=_picture(item), locations=spaces or None)
    if not found:
        logging.warning("Hauser & Wirth: no New York exhibition found; existing data kept.")
