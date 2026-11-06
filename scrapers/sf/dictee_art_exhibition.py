"""Dictée Art & Exhibition (2117 11th Ave, Oakland).

The gallery's Exhibitions page names its shows without dates, so the one place a run appears is the
home page's announcement of the next juried exhibition: a call for artists with the title in large
capitals over several lines ("MEMORY," / "LONGING," / "REMEMBERING"), a subtitle, a description and the run
("January 23 – March 6, 2027"). Only that announcement is read. The page is hand-edited, so if its layout
changes the scraper finds no title or dates and keeps the existing data.
"""
import logging
import re

from utils import fetch_and_parse
from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import page_lines, publish

HOME_URL = 'https://www.dictee.gallery/'
VENUE = 'Dictée Art & Exhibition'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')
_MAX_DESCRIPTION = 400


def _is_title_line(line):
    letters = re.sub(r'[^A-Za-z]', '', line)
    return len(letters) >= 3 and letters.isupper() and line != 'CALL FOR ARTISTS'


def scrape_dictee_art_exhibition(env='prod', region='sf'):
    """Scrape and process the next exhibition announced on Dictée's home page."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Dictée Art & Exhibition: could not fetch the home page; existing data kept.")
        return
    lines = [l.replace('​', '').strip() for l in page_lines(soup)]
    lines = [l for l in lines if l]
    run_at = next((i for i, l in enumerate(lines) if _RANGE_RE.match(l)), None)
    if run_at is None:
        logging.warning("Dictée Art & Exhibition: no dated exhibition found on the home page; existing data kept.")
        return
    # Walk back from the run over the description and subtitle to the block of capitalised title lines
    end = run_at
    while end > 0 and not _is_title_line(lines[end - 1]):
        end -= 1
    start = end
    while start > 0 and _is_title_line(lines[start - 1]):
        start -= 1
    title_lines = lines[start:end]
    if not title_lines:
        logging.warning("Dictée Art & Exhibition: could not read the exhibition's title; existing data kept.")
        return
    title = ' '.join(title_lines).title().replace(' ,', ',')
    after = lines[end:run_at]                      # subtitle first, then the description
    subtitle = after[0] if after and len(after[0]) < 80 else None
    name = f'{title}: {subtitle}' if subtitle else title
    description = ' '.join(after[1:] if subtitle else after)
    description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(description) > _MAX_DESCRIPTION else description
    start_date, end_date = parse_date_text(lines[run_at], today)
    if not publish(env, region, VENUE, name, start_date, end_date, HOME_URL, tag='gallery',
                   description=description or None):
        logging.info("Dictée Art & Exhibition: the announced exhibition has ended; nothing current to publish.")
