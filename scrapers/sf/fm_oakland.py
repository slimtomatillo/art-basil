"""FM Oakland (483 25th St, Oakland): a gallery and private studio space of ten artists.

The home page (a hand-edited OtherPeoplesPixels site) shows the exhibit now on view in its main block:
the show's picture, then a description with a short introduction, the title ("Paul Thompson: Life of a
Cowboy"), the artist's statement and the run ("October 2nd - November 28th, 2026"). The Current and
Upcoming pages list only names without dates, so only the home page is read. Past shows are listed
with their dates on the same page and are not published.
"""
import logging
import re
from urllib.parse import urljoin

from utils import fetch_and_parse
from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish

HOME_URL = 'https://fmoakland.com/home.html'
VENUE = 'FM Oakland'
_MAX_DESCRIPTION = 400
_ORDINAL = r'\d{1,2}(?:st|nd|rd|th)?'
_RUN_RE = re.compile(rf'[A-Z][a-z]+ {_ORDINAL}\s*,?\s*[-–]\s*[A-Z][a-z]+ {_ORDINAL},? \d{{4}}')
_QUOTE_STARTS = ('“', '"', '‘', "'")


def _read_show(lines):
    """(title, run text, intro) from the description's lines, or None. The run is the line with a date
    range; the title is the line before it (skipping the artist's quoted statement), or the text ahead of
    the dates when they share a line."""
    for i, line in enumerate(lines):
        run = _RUN_RE.search(line)
        if not run:
            continue
        before = line[:run.start()].strip(' -–,')
        if len(re.sub(r'[^A-Za-z]', '', before)) >= 3:
            title, head = before, lines[:i]
        else:
            j = i - 1
            while j >= 0 and lines[j].startswith(_QUOTE_STARTS):
                j -= 1
            if j < 0:
                return None
            title, head = lines[j], lines[:j]
        intro = ' '.join(l for l in head if len(l) > 100)
        return title, run.group(0), intro
    return None


def scrape_fm_oakland(env='prod', region='sf'):
    """Scrape and process the exhibit now on view at FM Oakland."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("FM Oakland: could not fetch the home page; existing data kept.")
        return
    block = soup.select_one('div.page div.description') or soup.select_one('div.description')
    lines = [' '.join(l.split()) for l in block.get_text('\n').split('\n')] if block else []
    show = _read_show([l for l in lines if l])
    if show is None:
        logging.warning("FM Oakland: no current exhibit with dates found on the home page; existing data kept.")
        return
    title, run, intro = show
    start_date, end_date = parse_date_text(run, today)
    if not (start_date or end_date):
        logging.warning(f"FM Oakland: no readable dates for {title!r}")
        return
    picture = soup.select_one('div.media-and-info img.u-img')
    image = urljoin('https:', picture['src']) if picture is not None and picture.get('src') else None
    description = intro[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(intro) > _MAX_DESCRIPTION else intro
    if not publish(env, region, VENUE, title, start_date, end_date, HOME_URL, tag='gallery',
                   description=description or None, image=image):
        logging.info("FM Oakland: the exhibit on the home page has ended; nothing current to publish.")
