from utils import fetch_and_parse
from images import candidate_images
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import date_label
from processing import region_today
import logging

LIST_URLS = ['https://galerie.uqam.ca/en/statut/current/', 'https://galerie.uqam.ca/en/statut/upcoming/']
VENUE = "Galerie de l'UQAM"
_NOT_A_SHOW_PICTURE = ('logo', 'calq', 'cca_', 'uqam_noir')


def _show_links(soup):
    """{url: title} for the exhibitions linked from a list page (each is linked twice: image and title)."""
    found = {}
    for a in soup.find_all('a', href=True):
        title = a.get_text(' ', strip=True)
        if '/en/expositions/' in a['href'] and title and not title.startswith('Virtual exhibition'):
            found[a['href']] = title
    return found


def _show_image(page, url):
    """The show's promo picture. The page's share image is the gallery's logo on every show, and the
    sponsors' logos follow the show's picture, so the first uploaded picture that isn't a logo is taken."""
    for src in candidate_images(page, url):
        name = src.rsplit('/', 1)[-1].lower()
        if '/wp-content/uploads/' in src and not any(word in name for word in _NOT_A_SHOW_PICTURE):
            return src
    return None


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
            stored += publish(env, region, VENUE, title, start, end, url, tag='gallery', seen=seen,
                              image=_show_image(page, url))
    if not fetched:
        logging.warning("Galerie de l'UQAM: could not fetch the exhibition lists; existing data kept.")
    elif not stored:
        logging.warning("Galerie de l'UQAM: no exhibitions found; existing data kept.")
