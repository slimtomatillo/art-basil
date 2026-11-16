"""Littman and White Galleries, Portland State University (Smith Memorial Student Union, 1825 SW Broadway): the shows on
littmanandwhite.com/exhibitions.

Each show is a few lines of text: its run in the gallery's own style ("10.26.26 - 01.22.27", the end sometimes only a month,
"01.xx.27"), the gallery it is in (Littman, White or the Microgalleries), the title (with "• artist" after it when there is
one), a description, and "Learn More", a link to the gallery's page. The student-run galleries show something new about once a
term; Converge 45 shows hosted elsewhere at PSU are not on this page.
"""
import calendar
import datetime as dt
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import clean
from scrapers.tor._common import publish
from utils import fetch_and_parse

VENUE = 'Littman and White Galleries'
PAGE_URL = 'https://www.littmanandwhite.com/exhibitions'
GALLERIES = ('Littman Gallery', 'White Gallery', 'Microgalleries')
_RUN = re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{2})\s*[-–—]\s*(\d{1,2})\.(\d{1,2}|xx)\.(\d{2})$', re.IGNORECASE)
_LONGEST_RUN_DAYS = 300        # a term-long show: a longer run is a typo in the year of its end


def parse_run(text):
    """(start, end) from "10.26.26 - 01.22.27"; "01.xx.27" is the last day of that month. (None, None) if not a run."""
    match = _RUN.match(clean(text))
    if not match:
        return None, None
    m1, d1, y1, m2, d2, y2 = match.groups()
    try:
        start = dt.date(2000 + int(y1), int(m1), int(d1))
        year, month = 2000 + int(y2), int(m2)
        day = calendar.monthrange(year, month)[1] if d2.lower() == 'xx' else int(d2)
        end = dt.date(year, month, day)
    except ValueError:
        return None, None
    if (end - start).days > _LONGEST_RUN_DAYS:                # "10.27.26 - 12.08.27" on the page, "12.08.26" on its home page
        try:
            end = end.replace(year=end.year - 1)
        except ValueError:
            pass
    return start, end if end >= start else None


def read_shows(soup, page_url):
    """[{name, start, end, gallery, description, link}] from the exhibitions page's lines of text."""
    lines = [clean(t) for t in soup.stripped_strings]
    shows = []
    for at, line in enumerate(lines):
        start, end = parse_run(line)
        if not start or at + 2 >= len(lines) or lines[at + 1] not in GALLERIES:
            continue
        title = lines[at + 2].split('•')[0].strip()
        artist = lines[at + 2].partition('•')[2].strip()
        paragraphs = []
        for text in lines[at + 3:]:
            if text.lower() == 'learn more' or parse_run(text)[0]:
                break
            paragraphs.append(text)
        shows.append({'name': title, 'artist': artist, 'start': start, 'end': end, 'gallery': lines[at + 1],
                      'description': ' '.join(paragraphs[:2]) or None})
    # "Learn More" links come in the same order as the shows
    links = [urljoin(page_url, a['href']) for a in soup.find_all('a', href=True) if clean(a.get_text(' ')).lower() == 'learn more']
    for show, link in zip(shows, links + [page_url] * len(shows)):
        show['link'] = link
    return shows


def scrape_psu_littman_white(env='prod', region='pdx'):
    """Scrape and process the shows at PSU's Littman and White Galleries."""
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Littman and White Galleries: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for show in read_shows(soup, PAGE_URL):
        name = f"{show['name']} • {show['artist']}" if show['artist'] else show['name']
        found += publish(env, region, VENUE, name, show['start'], show['end'], show['link'], tag='gallery',
                         description=show['description'], seen=seen)
    if not found:
        logging.warning("Littman and White Galleries: no current or upcoming exhibition found; existing data kept.")
