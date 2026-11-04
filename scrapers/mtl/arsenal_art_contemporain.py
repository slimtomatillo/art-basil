from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import date_label
from processing import region_today
from urllib.parse import urljoin
import logging

LIST_URL = 'https://www.arsenalcontemporary.com/montreal/expositions'
VENUE = 'Arsenal art contemporain'
DETAIL_PATH = '/montreal/expositions/details/'


def scrape_arsenal_art_contemporain(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at Arsenal art contemporain Montreal."""
    today = region_today(region)
    soup = fetch_and_parse(LIST_URL)
    if soup is None:
        logging.warning("Arsenal art contemporain: could not fetch the exhibitions page; existing data kept.")
        return
    # The list runs "EN COURS", "À VENIR", then the "PASSÉES" archive; only the shows above the archive are fetched
    past = soup.find(string=lambda s: s and s.strip() == 'PASSÉES')
    anchors = list(reversed(past.find_all_previous('a', href=True))) if past else soup.find_all('a', href=True)
    seen_urls, stored = [], 0
    for a in anchors:
        url = urljoin(LIST_URL, a['href'])
        if DETAIL_PATH in url and url not in seen_urls:
            seen_urls.append(url)
    for url in seen_urls:
        page = fetch_and_parse(url)
        if page is None:
            continue
        detail = page_lines(page)
        state_at = next((i for i, l in enumerate(detail) if l in ('En cours', 'À venir', 'Passée')), None)
        if state_at is None or detail[state_at] == 'Passée' or state_at < 1:
            continue
        # "Biennale ELEKTRA | En cours | 14 oct. | Écrit par | ... | BILLETTERIE | F(R)ICTION - Art et Jeux | ... | 15 octobre - 15 novembre 2026"
        # (the "4 août" on a page is the date it was posted; only a full range is taken as the show's dates)
        dated = next((i for i in range(state_at, len(detail)) if (label := date_label(detail[i], today)) and all(label)), None)
        if dated is None:
            continue
        name = detail[state_at - 1]
        after = detail[detail.index('BILLETTERIE') + 1] if 'BILLETTERIE' in detail else ''
        if after and after != name and len(after) <= 60 and not date_label(after, today):
            name = f"{name}: {after}"
        start, end = date_label(detail[dated], today)
        og = page.find('meta', property='og:image')
        stored += publish(env, region, VENUE, name, start, end, url, tag='gallery',
                          image=og.get('content') if og else None)
    if not stored:
        logging.warning("Arsenal art contemporain: no exhibitions found; existing data kept.")
