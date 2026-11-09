from utils import fetch_and_parse
from scrapers.tor._common import publish
from processing import region_today
import calendar
import datetime as dt
import logging
import re
from urllib.parse import urljoin

EXHIBITIONS_URL = 'https://wendemuseum.org/exhibitions/'
VENUE = 'Wende Museum'
# Runs are given by month: "Nov 2026-Jan 2027" under the title, in the "CURRENT" and "Upcoming" lists
_RANGE_RE = re.compile(r'^([A-Z][a-z]{2}) (\d{4})\s*[-–]\s*([A-Z][a-z]{2}) (\d{4})$')
_MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def _month_range(text):
    """'Nov 2026-Jan 2027' -> (Nov 1, 2026, Jan 31, 2027), or (None, None)."""
    m = _RANGE_RE.match(text)
    if not (m and m.group(1) in _MONTHS and m.group(3) in _MONTHS):
        return None, None
    y2, m2 = int(m.group(4)), _MONTHS[m.group(3)]
    return dt.date(int(m.group(2)), _MONTHS[m.group(1)], 1), dt.date(y2, m2, calendar.monthrange(y2, m2)[1])


def _card_picture(card):
    """The card's picture: the lazy-loaded image's real address (src holds a placeholder until it loads)."""
    img = card.select_one('img')
    url = (img.get('data-src') or img.get('src') or '') if img else ''
    return url if url.startswith('http') else None


def scrape_wende_museum(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at the Wende Museum (a free museum)."""
    region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Wende Museum: could not fetch the exhibitions page; existing data kept.")
        return
    # Each exhibition is a slider card: a type label ("Exhibition"), the run ("Nov 2026-Jan 2027"), the title,
    # a link to its own page and a picture. (The page text alone can't tell the label from the title.)
    seen = set()
    stored = 0
    for card in soup.select('.hero-slider__item'):
        date_tag, title_tag, link_tag = (card.select_one('.more-date'), card.select_one('.title'),
                                         card.select_one('a[href]'))
        if not (date_tag and title_tag):
            continue
        start_date, end_date = _month_range(date_tag.get_text(' ', strip=True))
        # One entry puts a notice after the name ("Bumdog Torres | THIS STRUCTURE WILL BE REMOVED...")
        title = title_tag.get_text(' ', strip=True).split(' | ')[0]
        if not (title and start_date):
            continue
        stored += publish(env, region, VENUE, title, start_date, end_date,
                          urljoin(EXHIBITIONS_URL, link_tag['href']) if link_tag else EXHIBITIONS_URL,
                          tag='museum', extra_tags=('free',), seen=seen, image=_card_picture(card))
    if not stored:
        logging.warning("Wende Museum: no exhibitions found; existing data kept.")
