from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import date_label
from processing import region_today
from urllib.parse import parse_qs, urlparse
import logging
import re

ON_VIEW_URL = 'https://ellengallery.concordia.ca/programmation/en-salle/'
VENUE = 'Leonard & Bina Ellen Art Gallery'


def scrape_ellen_art_gallery(env='prod', region='mtl'):
    """Scrape and process the exhibition on view at the Leonard & Bina Ellen Art Gallery (Concordia)."""
    today = region_today(region)
    soup = fetch_and_parse(ON_VIEW_URL)
    if soup is None:
        logging.warning("Ellen Art Gallery: could not fetch the on-view page; existing data kept.")
        return
    # The "En salle" page is the current show's page. Its own address is only given in a Facebook share link
    # ("sharer.php?u=https://ellengallery.concordia.ca/exposition/<show>/").
    url = next((parse_qs(urlparse(a['href']).query).get('u', [None])[0] for a in soup.find_all('a', href=True)
                if 'sharer.php' in a['href']), None)
    if not (url and '/exposition/' in url):
        logging.warning("Ellen Art Gallery: no exhibition page linked from the on-view page; existing data kept.")
        return
    page = fetch_and_parse(url)
    if page is None or page.title is None:
        logging.warning("Ellen Art Gallery: could not fetch the exhibition page; existing data kept.")
        return
    name = re.split(r'\s+[|–—-]\s+', re.sub(r'\s+', ' ', page.title.get_text()).strip())[0]
    label = next((date_label(l, today) for l in page_lines(page) if date_label(l, today)), None)
    if not (name and label):
        logging.warning("Ellen Art Gallery: no dates found on the exhibition page; existing data kept.")
        return
    og = page.find('meta', property='og:image')
    publish(env, region, VENUE, name.title() if name.isupper() else name, label[0], label[1], url, tag='gallery',
            image=og.get('content') if og else None)
