from utils import fetch_and_parse
from scrapers.tor._common import publish
from processing import region_today
import datetime as dt
import logging
import re
from urllib.parse import urljoin

LIST_URLS = ['https://fonderiedarling.org/en/exhibition-on-view', 'https://fonderiedarling.org/en/upcoming-exhibitions']
VENUE = 'Fonderie Darling'
# Pages link relative to <base href="https://fonderiedarling.org/en/">
BASE_URL = 'https://fonderiedarling.org/en/'
# Each show is a div.post: a picture, then <h2><span class="artist">Shanie Tomassini</span> / <a>Solar
# Lamentation</a></h2> and <h3 class="date"> holding two <moment date="2026-09-17"> tags. The page fills
# those tags in with JavaScript, so its visible text has no dates; the ISO dates in the tags are read.


def _iso(tag):
    try:
        return dt.date.fromisoformat(tag.get('date', '')[:10])
    except ValueError:
        return None


def read_posts(soup):
    """Yield (name, start, end, page url, picture url) for each show on a list page."""
    for post in soup.find_all('div', class_='post'):
        heading = post.find('h2')
        title_link = heading.find('a', href=True) if heading else None
        if not title_link:
            continue
        title = ' '.join(title_link.get_text(' ', strip=True).split())
        artist = heading.find('span', class_='artist')
        artist = ' '.join(artist.get_text(' ', strip=True).split()).strip(' /') if artist else ''
        days = [_iso(m) for m in post.select('h3.date moment')]
        start = days[0] if days else None
        end = days[1] if len(days) > 1 else None
        img = post.find('img', src=True)
        yield (f'{artist}: {title}' if artist else title, start, end,
               urljoin(BASE_URL, title_link['href']), urljoin(BASE_URL, img['src']) if img else None)


def scrape_fonderie_darling(env='prod', region='mtl'):
    """Scrape and process the exhibitions on view and upcoming at Fonderie Darling."""
    region_today(region)
    seen = set()
    fetched = stored = 0
    for list_url in LIST_URLS:
        soup = fetch_and_parse(list_url)
        if soup is None:
            continue
        fetched += 1
        for name, start, end, url, image in read_posts(soup):
            stored += publish(env, region, VENUE, name, start, end, url, tag='gallery', seen=seen, image=image)
    if not fetched:
        logging.warning("Fonderie Darling: could not fetch the exhibition lists; existing data kept.")
    elif not stored:
        logging.warning("Fonderie Darling: no exhibitions found; existing data kept.")
