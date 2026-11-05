from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import date_label
from processing import region_today
import logging

ON_VIEW_URL = 'https://rmk-museum.org.tr/istanbul/sergiler/devam-eden-sergiler'
VENUE = 'Rahmi M. Koç Museum'


def scrape_rahmi_koc_museum(env='prod', region='ist'):
    """Scrape and process the exhibitions on view at the Rahmi M. Koç Museum in Istanbul (not its Ankara, Ayvalık or Cunda museums)."""
    today = region_today(region)
    soup = fetch_and_parse(ON_VIEW_URL)
    if soup is None:
        logging.warning("Rahmi M. Koç Museum: could not fetch the on-view page; existing data kept.")
        return
    lines = page_lines(soup)
    # "Devam Eden Sergiler | Geçmiş Sergiler | 09 Ekim 2026 - 07 Şubat 2027 | Yerli Sanayi, Uluslararası İtibar | description..."
    begin = lines.index('Geçmiş Sergiler') + 1 if 'Geçmiş Sergiler' in lines else 0
    end = next((i for i, l in enumerate(lines) if i > begin and l == 'ÇALIŞMA SAATLERİMİZ'), len(lines))
    listing = Listing(env, region, VENUE, soup, ON_VIEW_URL)
    for i in range(begin, end - 1):
        label = date_label(lines[i], today)
        if label and all(label):
            listing.add(lines[i + 1], label[0], label[1], tag='museum')
    if not listing.publish():
        logging.warning("Rahmi M. Koç Museum: no exhibitions found; existing data kept.")
