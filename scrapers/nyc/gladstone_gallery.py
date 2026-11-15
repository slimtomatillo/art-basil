"""Gladstone Gallery: the New York shows in its listing page's data file.

https://gladstonegallery.com/exhibitions/ is a Gatsby page that fills itself in the browser from
/page-data/exhibitions/page-data.json: data.allContentfulExhibition.nodes lists every show of every city (and the past
ones) with artists, title, startDate and endDate ("2026-11-12"), slug, location ("New York: 24th Street") and region.
Only region "New York" is kept; each show is stored with the space its location names. A show with no title is the
artist's name alone.
"""
import datetime as dt
import json
import logging
import re

from processing import region_today
from scrapers.nyc._common import clean
from scrapers.tor._common import publish
from utils import fetch_json

DATA_URL = 'https://gladstonegallery.com/page-data/exhibitions/page-data.json'
SHOW_URL = 'https://gladstonegallery.com/exhibitions/'
VENUE = 'Gladstone Gallery'
# (label, regex for the show's location); the addresses are in docs/data/nyc_venues.json under the same labels
SPACES = [('21st Street', r'21st'), ('24th Street', r'24th'), ('64th Street', r'64th'), ('Lenox Avenue', r'Lenox')]
_PICTURE = re.compile(r'https://images\.ctfassets\.net/[^\s"\\,]+?\.(?:jpg|jpeg|png)', re.IGNORECASE)


def _day(text):
    try:
        return dt.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _picture(node):
    match = _PICTURE.search(json.dumps((node.get('tileImage') or {})))
    return match.group(0) + '?w=1200&q=80' if match else None


def scrape_gladstone_gallery(env='prod', region='nyc'):
    """Scrape and process Gladstone Gallery's New York exhibitions."""
    today = region_today(region)
    data = fetch_json(DATA_URL)
    try:
        nodes = data['result']['data']['allContentfulExhibition']['nodes']
    except (KeyError, TypeError):
        logging.warning("Gladstone Gallery: could not read the exhibitions data; existing data kept.")
        return
    found = 0
    seen = set()
    shows = {}                                  # name -> (first node, spaces): one show can be at two spaces, each its own entry
    for node in nodes:
        if clean(node.get('region')) != 'New York' or not node.get('slug'):
            continue
        start_date, end_date = _day(node.get('startDate')), _day(node.get('endDate'))
        if not (start_date or end_date) or (end_date and end_date < today):
            continue
        artists = ', '.join(clean(a.get('name')) for a in node.get('artists') or [] if a.get('name'))
        title = clean(node.get('title'))
        name = f'{artists}: {title}' if artists and title else (artists or title)
        location = clean(node.get('location'))
        spaces = [label for label, pattern in SPACES if re.search(pattern, location)] or None
        if not name:
            continue
        first, known = shows.setdefault(name, (node, []))
        known += [s for s in spaces or [] if s not in known]
    for name, (node, spaces) in shows.items():
        found += publish(env, region, VENUE, name, _day(node.get('startDate')), _day(node.get('endDate')),
                         f"{SHOW_URL}{node['slug']}/", tag='gallery', seen=seen, image=_picture(node), locations=spaces or None)
    if not found:
        logging.warning("Gladstone Gallery: no New York exhibition found; existing data kept.")
