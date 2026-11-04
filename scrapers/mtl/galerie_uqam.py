from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import date_label
from processing import region_today
import logging

LIST_URLS = ['https://galerie.uqam.ca/en/statut/current/', 'https://galerie.uqam.ca/en/statut/upcoming/']
VENUE = "Galerie de l'UQAM"


def _show_links(soup):
    """{url: title} for the exhibitions linked from a list page (each is linked twice: image and title)."""
    found = {}
    for a in soup.find_all('a', href=True):
        title = a.get_text(' ', strip=True)
        if '/en/expositions/' in a['href'] and title and not title.startswith('Virtual exhibition'):
            found[a['href']] = title
    return found


def scrape_galerie_uqam(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at Galerie de l'UQAM (its virtual and touring shows are left out)."""
    today = region_today(region)
    seen = set()
    fetched = stored = 0
    for list_url in LIST_URLS:
        soup = fetch_and_parse(list_url)
        if soup is None:
            continue
        fetched += 1
        for url, title in _show_links(soup).items():
            page = fetch_and_parse(url)
            if page is None:
                continue
            lines = page_lines(page)
            # A show in the gallery has "November 6, 2026 - January 16, 2027" followed by "Opening:";
            # a touring one (at another museum) has no opening line, and some upcoming shows have no dates yet
            at = next((i for i, l in enumerate(lines) if date_label(l, today) and lines[i + 1:i + 2] == ['Opening:']), None)
            if at is None:
                continue
            start, end = date_label(lines[at], today)
            og = page.find('meta', property='og:image')
            stored += publish(env, region, VENUE, title, start, end, url, tag='gallery', seen=seen,
                              image=og.get('content') if og else None)
    if not fetched:
        logging.warning("Galerie de l'UQAM: could not fetch the exhibition lists; existing data kept.")
    elif not stored:
        logging.warning("Galerie de l'UQAM: no exhibitions found; existing data kept.")
