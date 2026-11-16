"""Chefas Projects (formerly Stephanie Chefas Projects), 134 SE Taylor St: stephaniechefas.com.

/exhibits is the show on view: its title ("KRISTEN DIEDERICH | OUTSIDE NATURE - CHEFAS PROJECTS"), a line with the run
("OCTOBER 23 - NOVEMBER 21, 2026"), a description and a picture. /upcomingexhibits lists the next shows as a name and a line
that so far says only when it opens ("OPENS DECEMBER 4, 2026"); a show with no end date is held back until the page gives
a run, so nothing is shown as running with no end.
"""
import logging
import re

from processing import region_today
from scrapers.nyc._common import clean, parse_dates, title_case
from scrapers.nyc._pages import _description, _meta, _picture
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Chefas Projects'
CURRENT_URL = 'https://www.stephaniechefas.com/exhibits'
UPCOMING_URL = 'https://www.stephaniechefas.com/upcomingexhibits'
_SUFFIX = re.compile(r'\s+-\s+CHEFAS PROJECTS$', re.IGNORECASE)


def current_name(soup):
    """"Kristen Diederich: Outside Nature" from the page's title, or ''."""
    title = _SUFFIX.sub('', _meta(soup, property='og:title') or (clean(soup.title.get_text(' ')) if soup.title else ''))
    return title_case(title.replace(' | ', ': ')) if title and 'chefas projects' not in title.lower() else ''


def current_run(soup, today):
    """(start, end) from the first line near the top that gives a full run."""
    for line in [clean(t) for t in soup.stripped_strings][:80]:
        start, end = parse_dates(line, today)
        if start and end:
            return start, end
    return None, None


def upcoming_shows(soup, today):
    """[(name, start, end)] for the listed shows whose line gives a full run; those that only say when they open are left out."""
    lines = [clean(t) for t in soup.stripped_strings]
    shows = []
    for at, line in enumerate(lines):
        if at and re.match(r'^(?:opens?|opening)\b', line, re.IGNORECASE) is None and re.search(r'\d{4}', line):
            start, end = parse_dates(line, today)
            if start and end:
                shows.append((title_case(lines[at - 1]), start, end))
    return shows


def scrape_chefas_projects(env='prod', region='pdx'):
    """Scrape and process Chefas Projects' current and upcoming exhibitions."""
    today = region_today(region)
    found = 0
    seen = set()
    page = fetch_and_parse(CURRENT_URL)
    if page is None:
        logging.warning("Chefas Projects: could not fetch the exhibits page; existing data kept.")
    else:
        name = current_name(page)
        start, end = current_run(page, today)
        if name and start and end:
            found += publish(env, region, VENUE, name, start, end, CURRENT_URL, tag='gallery', description=_description(page, name),
                             image=_picture(page, CURRENT_URL), seen=seen)
    upcoming = fetch_and_parse(UPCOMING_URL)
    if upcoming is not None:
        for name, start, end in upcoming_shows(upcoming, today):
            found += publish(env, region, VENUE, name, start, end, UPCOMING_URL, tag='gallery', seen=seen)
    if not found:
        logging.warning("Chefas Projects: no current or upcoming exhibition found; existing data kept.")
