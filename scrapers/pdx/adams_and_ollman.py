"""Adams and Ollman, 418 NW 8th Ave: the exhibitions at adamsandollman.com/Current-Exhibitions and /Upcoming-Exhibitions.

Both pages are a short list of lines of text with no link or picture per show: the title (an artist's name, and a show title
on a second line when it has one), then its run ("February 13–March 27, 2027"). A page with no show on it is just its menu.
Each show is linked to the page it was listed on.
"""
import logging

from processing import region_today
from scrapers.nyc._common import clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Adams and Ollman'
PAGES = ['https://adamsandollman.com/Current-Exhibitions', 'https://adamsandollman.com/Upcoming-Exhibitions']
_MENU = ('current', 'upcoming', 'past')


def read_shows(soup, today):
    """[(name, start, end)] from a listing page: the lines after its Current / Upcoming / Past menu, grouped by the date line
    that ends each show."""
    blocks = soup.find_all('projectcontent')
    if not blocks:
        return []
    lines = [clean(t) for t in blocks[-1].stripped_strings]
    lines = [line for line in lines if line]
    while lines and lines[0].lower() in _MENU:
        lines.pop(0)
    shows, name = [], []
    for line in lines:
        start, end = parse_dates(line, today)
        if (start or end) and name:
            shows.append((' '.join(name), start, end))
            name = []
        elif not (start or end):
            name.append(line)
    return shows


def scrape_adams_and_ollman(env='prod', region='pdx'):
    """Scrape and process Adams and Ollman's current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    for page in PAGES:
        soup = fetch_and_parse(page)
        if soup is None:
            logging.warning(f"Adams and Ollman: could not fetch {page}; existing data kept.")
            continue
        for name, start_date, end_date in read_shows(soup, today):
            found += publish(env, region, VENUE, name, start_date, end_date, page, tag='gallery', seen=seen)
    if not found:
        logging.warning("Adams and Ollman: no current or upcoming exhibition found; existing data kept.")
