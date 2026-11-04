from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from processing import region_today
import datetime as dt
import logging
import re
from urllib.parse import urljoin

BASE_URL = 'https://molaa.org/'
EXHIBITIONS_URL = 'https://molaa.org/exhibitions/'
VENUE = 'Museum of Latin American Art'
# Each show has its own page at /<year>-<name>, linked from a row of slides; the dates sit under the title
# as "Starting October 4, 2026 - February 21, 2027" (some pages give only the opening day)
_SLIDE_HREF_RE = re.compile(r'^(?:https?://molaa\.org)?/20\d\d-[\w-]+$')
_DATES_RE = re.compile(r'^Starting ([A-Z][a-z]+ \d{1,2}, \d{4})(?:\s*[-–]\s*([A-Z][a-z]+ \d{1,2}, \d{4}))?')


def _date(text):
    try:
        return dt.datetime.strptime(text, '%B %d, %Y').date() if text else None
    except ValueError:
        return None


def _title(lines, dates_at):
    """The heading above the dates: the lines after the site menu, e.g. "Antonio Romero:" + "TROPICALIA [VOL2]"."""
    parts = []
    for line in reversed(lines[max(0, dates_at - 5):dates_at]):
        if line in ('Donate', 'Become A Member') or line.startswith(('ORGANIZED BY', 'Exhibition Brochure')):
            if line in ('Donate', 'Become A Member'):
                break
            continue
        parts.insert(0, line)
    if not parts:
        return None
    return ' '.join(parts) if parts[0].endswith(':') else ': '.join(parts)


def _title_card(page):
    """The show's own graphic (its title set in type, named like "...Logo.jpg"): the first lazy-loaded
    picture on its page, ahead of the museum's anniversary logo, footer and sponsor pictures. The pages
    have no share image and no photo, and this is the only thing that belongs to the show."""
    img = page.select_one('img[data-src]')
    return urljoin('https:', img['data-src']) if img else None


def scrape_molaa(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at the Museum of Latin American Art."""
    region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("MOLAA: could not fetch the exhibitions page; existing data kept.")
        return
    links = []
    # The slides run current shows first; an empty slide separates them from the past ones
    for a in soup.select('a.image-slide-anchor'):
        href = a.get('href')
        if not href:
            break
        if _SLIDE_HREF_RE.match(href) and href not in links:
            links.append(href)
    seen = set()
    stored = 0
    for href in links:
        url = urljoin(BASE_URL, href)
        page = fetch_and_parse(url)
        if page is None:
            continue
        lines = page_lines(page)
        dates_at = next((i for i, l in enumerate(lines) if _DATES_RE.match(l)), None)
        if dates_at is None:
            continue
        m = _DATES_RE.match(lines[dates_at])
        name = _title(lines, dates_at)
        og = page.find('meta', property='og:image')
        stored += publish(env, region, VENUE, name, _date(m.group(1)), _date(m.group(2)), url,
                          tag='museum', seen=seen, image=og.get('content') if og else _title_card(page))
    if not stored:
        logging.warning("MOLAA: no exhibitions found; existing data kept.")
