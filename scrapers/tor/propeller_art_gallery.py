from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

HOME_URL = 'https://propellerartgallery.com/'
_SHOW_URL_RE = re.compile(r'^https://propellerartgallery\.com/exhibitions/[^/?]+/$')
# "September 30 – October 18, 2026" under the title and artist on each show's page
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [–-] (?:[A-Z][a-z]+ )?\d{1,2}, \d{4}$')


def scrape_propeller_art_gallery(env='prod', region='tor'):
    """Scrape and process the shows linked from the Propeller Art Gallery home page."""
    today = region_today(region)
    home = fetch_and_parse(HOME_URL)
    if home is None:
        logging.warning("Propeller Art Gallery: could not fetch the home page; existing data kept.")
        return
    urls = []
    for a in home.find_all('a', href=True):
        if _SHOW_URL_RE.match(a['href']) and a['href'] not in urls:
            urls.append(a['href'])

    found = 0
    for url in urls:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        lines = page_lines(soup)
        i = next((k for k, l in enumerate(lines) if k >= 2 and _RANGE_RE.match(l)), None)
        if i is None:
            logging.warning(f"Propeller Art Gallery: no date range on {url}")
            continue
        start_date, end_date = parse_date_text(lines[i], today)
        # Title and artist are either one line ("Desert Frequencies | Jelena Duma") or two lines,
        # the title in capitals ("ALL THE LIVING THINGS" / "Tracy Thomson")
        if ' | ' in lines[i - 1]:
            name = lines[i - 1].replace(' | ', ': ')
        else:
            title = lines[i - 2]
            name = f'{title.title() if title.isupper() else title}: {lines[i - 1]}'
        found += publish(env, region, 'Propeller Art Gallery', name, start_date, end_date, url, tag='gallery')
    if not found:
        logging.warning("Propeller Art Gallery: no current or upcoming shows found; existing data kept.")
