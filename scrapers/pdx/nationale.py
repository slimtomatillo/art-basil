"""Nationale, 15 SE 22nd Ave: a bookshop and gallery (nationale.us) with a Front Gallery and a Project Room.

Its menu links the current show, the upcoming ones and the Project Room. A show's page gives the artist ("GABI VILLASEÑOR //"),
the title, and a line with its run, "On view in the Front Space October 17–November 21, 2026". The upcoming page so far
gives only the opening reception's date ("Opening reception November 28, 2026"), which is not a run, so a show with no
"On view" line is held back until one appears. Only that line is read as dates.
"""
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import clean, parse_dates, title_case
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Nationale'
HOME_URL = 'https://www.nationale.us/'
MENU = ('current', 'upcoming', 'project room')
_ON_VIEW = re.compile(r'^On view(?: in the [A-Za-z ]+?)?\s+((?:[A-Z][a-z]+)\s+\d.*\d{4})$')


def menu_links(soup, page_url):
    """The pages the exhibitions menu links to (Current, Upcoming, Project Room), once each."""
    found = []
    for a in soup.find_all('a', href=True):
        if clean(a.get_text(' ')).lower() in MENU:
            url = urljoin(page_url, a['href']).split('#')[0]
            if url not in found:
                found.append(url)
    return found


def read_shows(soup, today):
    """[(name, start, end)] from a show page: the lines above each "On view ..." line are its title and, above that, the artist."""
    lines = [clean(t) for t in soup.stripped_strings]
    shows = []
    for at, line in enumerate(lines):
        match = _ON_VIEW.match(line)
        if not match or at < 1:
            continue
        start, end = parse_dates(match.group(1), today)
        if not (start and end):
            continue
        title = lines[at - 1].strip('“”"')
        artist = lines[at - 2] if at >= 2 and lines[at - 2].endswith('//') else ''
        artist = title_case(artist.rstrip('/ ').strip())
        shows.append((f'{artist}: {title}' if artist else title, start, end))
    return shows


def scrape_nationale(env='prod', region='pdx'):
    """Scrape and process Nationale's current, upcoming and Project Room exhibitions."""
    today = region_today(region)
    home = fetch_and_parse(HOME_URL)
    if home is None:
        logging.warning("Nationale: could not fetch the home page; existing data kept.")
        return
    found = 0
    seen = set()
    for url in menu_links(home, HOME_URL):
        page = fetch_and_parse(url)
        if page is None:
            continue
        for name, start, end in read_shows(page, today):
            found += publish(env, region, VENUE, name, start, end, url, tag='gallery', seen=seen)
    if not found:
        logging.warning("Nationale: no current or upcoming exhibition found; existing data kept.")
