from utils import fetch_and_parse
from scrapers.tor._common import publish
from scrapers.la._gallery import date_label
from processing import region_today
import logging
import time

PAGE_URL = 'https://laguilde.com/pages/expositions'
VENUE = 'La Guilde'
PICTURE_WIDTH = 1080
# The site (Shopify behind Cloudflare) sometimes rate-limits the default "Your Bot 0.1" agent with a 429
BROWSER_HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                 '(KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
RETRY_AFTER = 45
# A Shopify page listing every show, current and upcoming first, then past years. Each show is a
# div.grid__item linking to /blogs/expositions/<slug>, holding a picture, an <h3> that is either the
# artist or a kind of show ("Exposition collective"), then a div.rte-setting with the title on one or two
# heading lines and the dates in French: "Du 8 octobre au 14 novembre 2026". Past shows are skipped
# by publish(). Casing is set by CSS, so the source text mixes ALL CAPS and stray capitals.
SHOW_KINDS = ('exposition', 'marché', 'marche')


def _tidy(text):
    text = ' '.join(text.split()).strip()
    return text.capitalize() if text.isupper() else text


def read_shows(soup, today):
    """Yield (name, start, end, page url, picture url) for each show on the page."""
    for item in soup.select('div.grid__item'):
        link = item.find('a', href=lambda h: h and '/blogs/expositions/' in h)
        body = item.find('div', class_='rte-setting')
        if not (link and body):
            continue
        dates = next((date_label(p.get_text(' ', strip=True), today) for p in body.find_all('p')
                      if date_label(p.get_text(' ', strip=True), today)), None)
        if not dates:
            continue
        title = ' '.join(_tidy(h.get_text(' ', strip=True)) for h in body.find_all(['h2', 'h3']))
        title = title.strip().rstrip(':')
        # The <h3> above the title block: the artist, or a kind of show that isn't part of the name
        label = next((h.get_text(' ', strip=True) for h in item.find_all('h3') if body not in h.parents), '')
        if label and not label.lower().startswith(SHOW_KINDS):
            title = f'{label.title()}: {title}'
        img = item.find('img', attrs={'data-src': True})
        picture = None
        if img:
            picture = img['data-src'].replace('{width}', str(PICTURE_WIDTH))
            picture = 'https:' + picture if picture.startswith('//') else picture
        url = link['href'] if link['href'].startswith('http') else 'https://laguilde.com' + link['href']
        yield title, dates[0], dates[1], url, picture


def scrape_la_guilde(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at La Guilde."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL, headers=BROWSER_HEADERS)
    if soup is None:
        # Shopify answers 429 when it has seen several quick requests; it clears within a minute or so
        time.sleep(RETRY_AFTER)
        soup = fetch_and_parse(PAGE_URL, headers=BROWSER_HEADERS)
    if soup is None:
        logging.warning("La Guilde: could not fetch the exhibitions page; existing data kept.")
        return
    seen = set()
    stored = 0
    for name, start, end, url, image in read_shows(soup, today):
        stored += publish(env, region, VENUE, name, start, end, url, tag='gallery', seen=seen, image=image)
    if not stored:
        logging.warning("La Guilde: no current or upcoming exhibitions found; existing data kept.")
