from utils import fetch_and_parse
from scrapers.tor._common import publish
from processing import region_today
import calendar
import datetime as dt
import logging
import re
from urllib.parse import urljoin

EXHIBITIONS_URL = 'https://www.cca.qc.ca/en/about-exhibitions'
VENUE = 'Canadian Centre for Architecture'
# A show's own page, e.g. /en/events/102331/reframing-the-american-landscape
_SHOW_LINK_RE = re.compile(r'^(?:https://www\.cca\.qc\.ca)?/en/events/\d+/[^/?#]+$')
# Each show page heads its dates "Exhibition, Octagonal Gallery," followed by two
# <span class="dt"> dates: "1 October 2026" to "3 January 2027", or just "April 2027" to "March 2028".
#
# The exhibitions page itself only gives one date per show in a sentence ("is on display ... until
# 10 January 2027"), which is sometimes out of date, and it leaves some upcoming shows out. The full
# list of current and upcoming shows is in the menu every show page carries, so that is read too.


def _show_links(soup, base):
    """{url: title} for the show pages linked from a page."""
    found = {}
    for a in soup.find_all('a', href=True):
        title = a.get_text(' ', strip=True)
        if title and _SHOW_LINK_RE.match(a['href']):
            found.setdefault(urljoin(base, a['href']), title)
    return found


def _parse_day(text, last=False):
    """'1 October 2026' -> that date; 'April 2027' -> 1 April (or 30 April with last=True)."""
    text = ' '.join(text.split())
    for fmt in ('%d %B %Y', '%B %Y'):
        try:
            day = dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if fmt == '%B %Y' and last:
            day = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        return day
    return None


def show_dates(page):
    """(start, end) from a show page, or None if it isn't an exhibition or has no readable dates."""
    # The menu's "Through 8 November" entries are also div.date; the show's own one is in its header
    block = page.select_one('.cal-event-header div.date')
    cat = block.find('span', class_='cat') if block else None
    if not (cat and cat.get_text(strip=True).startswith('Exhibition')):
        return None
    days = [span.get_text(' ', strip=True) for span in block.find_all('span', class_='dt')]
    if not days:
        return None
    start = _parse_day(days[0])
    end = _parse_day(days[1], last=True) if len(days) > 1 else None
    return (start, end) if (start or end) else None


def scrape_cca(env='prod', region='mtl'):
    """Scrape and process the shows on view and upcoming at the Canadian Centre for Architecture."""
    region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("CCA: could not fetch the exhibitions page; existing data kept.")
        return
    shows = _show_links(soup, EXHIBITIONS_URL)
    if not shows:
        logging.warning("CCA: no exhibitions linked from the exhibitions page; existing data kept.")
        return
    pages, queue, menu_read = {}, list(shows), False
    while queue:
        url = queue.pop(0)
        if url in pages:
            continue
        pages[url] = fetch_and_parse(url)
        if pages[url] is None:
            continue
        # The menu on every show page lists all current and upcoming shows, including ones the
        # exhibitions page leaves out; one show page is enough to find them
        if not menu_read:
            menu_read = True
            for link, title in _show_links(pages[url], url).items():
                if link not in shows:
                    shows[link] = title
                    queue.append(link)
    seen = set()
    stored = 0
    for url, title in shows.items():
        page = pages.get(url)
        dates = show_dates(page) if page is not None else None
        if not dates:
            continue
        og = page.find('meta', property='og:image')
        stored += publish(env, region, VENUE, title, dates[0], dates[1], url, tag='museum', seen=seen,
                          image=og.get('content') if og else None)
    if not stored:
        logging.warning("CCA: no exhibitions found; existing data kept.")
