"""Daniel Faria Gallery, 188 St Helens Ave, Toronto.

The exhibitions page is filled in by JavaScript from the site's public WordPress GraphQL endpoint
(https://api.danielfariagallery.com/graphql), so the shows are read from there directly: no browser
rendering and no proxy needed. The newest shows come first; each has a title, its artists and
dates written like "November 12, 2026". "Closed for installation" entries mark gaps between
shows and are skipped.
"""
import datetime as dt
import logging

from scrapers.tor._common import publish
from utils import fetch_json

API_URL = 'https://api.danielfariagallery.com/graphql'
SITE_URL = 'https://danielfariagallery.com'
VENUE = 'Daniel Faria Gallery'
# 20 is several years of shows; only the first few can still be current or upcoming
QUERY = '''
query {
  exhibitions(first: 20) {
    nodes {
      title uri
      featuredImage { node { url: mediaItemUrl } }
      custom { startDate endDate artists: artist { ... on Artist { name: title } } }
    }
  }
}'''


def _date(text):
    try:
        return dt.datetime.strptime(' '.join((text or '').split()), '%B %d, %Y').date()
    except ValueError:
        return None


def scrape_daniel_faria_gallery(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at Daniel Faria Gallery."""
    data = fetch_json(API_URL, query=QUERY)
    nodes = ((data or {}).get('data') or {}).get('exhibitions', {}).get('nodes') if data else None
    if not nodes:
        logging.warning("Daniel Faria Gallery: no exhibitions from the site's API; existing data kept.")
        return
    found = 0
    seen = set()
    for node in nodes:
        title = ' '.join((node.get('title') or '').split())
        custom = node.get('custom') or {}
        if not title or title.lower().startswith('closed for installation'):
            continue
        start_date, end_date = _date(custom.get('startDate')), _date(custom.get('endDate'))
        artists = [a['name'] for a in (custom.get('artists') or []) if a and a.get('name')]
        # A solo show is named for its artist; a group show keeps just its title
        name = f'{artists[0]}: {title}' if len(artists) == 1 else title
        image = (((node.get('featuredImage') or {}).get('node')) or {}).get('url')
        found += publish(env, region, VENUE, name, start_date, end_date, SITE_URL + (node.get('uri') or '/exhibitions'),
                         tag='gallery', seen=seen, image=image)
    if not found:
        logging.warning("Daniel Faria Gallery: no current or upcoming exhibitions (between shows?); existing data kept.")
