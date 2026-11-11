"""Root Division, 1131 Mission St, San Francisco: the exhibitions on its gallery page.

https://rootdivision.org/gallery/exhibitions/ is a WordPress list (the Content Views plugin) of the
current and upcoming shows: a picture, the title, "Exhibition Dates: November 14 – December 19,
2026" and a Read More link to the show's own page. Between shows the list is empty ("No posts
found"), which is normal. The show's page has the description; its og:description is left over
from another show, so it is not used.
"""
import logging

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://rootdivision.org/gallery/exhibitions/'
VENUE = 'Root Division'
_MAX_DESCRIPTION = 400


def _description(url):
    """The first paragraphs of the show's page, or None."""
    soup = fetch_and_parse(url)
    article = soup.find('article') if soup else None
    if article is None:
        return None
    paragraphs = [' '.join(p.get_text().split()) for p in article.find_all('p')]
    text = ' '.join(p for p in paragraphs if len(p) > 60)
    if len(text) > _MAX_DESCRIPTION:
        text = text[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
    return text or None


def scrape_root_division(env='prod', region='sf'):
    """Scrape and process the exhibitions listed on Root Division's gallery page."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Root Division: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for item in soup.select('.pt-cv-content-item'):
        link = item.select_one('.pt-cv-title a[href]')
        dates = item.select_one('.pt-cv-ctf-value')
        if link is None or dates is None:
            continue
        name = ' '.join(link.get_text(' ').split())
        start_date, end_date = parse_date_text(dates.get_text(' '), today)
        if not (start_date or end_date):
            logging.warning(f"Root Division: no readable dates for {name!r}")
            continue
        picture = item.select_one('img.pt-cv-thumbnail')
        found += publish(env, region, VENUE, name, start_date, end_date, link['href'], tag='gallery',
                         description=_description(link['href']), seen=seen,
                         image=picture.get('src') if picture else None)
    if not found:
        logging.warning("Root Division: no current or upcoming exhibition listed; existing data kept.")
