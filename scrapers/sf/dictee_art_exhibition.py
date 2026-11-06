"""Dictée Art & Exhibition (2117 11th Ave, Oakland).

The gallery's Exhibitions page names its shows without dates, so the one place a run appears is the
home page's announcement of the next juried exhibition: a call for artists with the title in large
capitals over several lines ("MEMORY," / "LONGING," / "REMEMBERING"), a subtitle, a description and the run
("January 23 – March 6, 2027"). Only that announcement is read. The page is hand-edited, so if its layout
changes the scraper finds no title or dates and keeps the existing data.

The show's picture is the announcement section's background, a Wix image the page lists in the
data-image-info of a <wow-image> element rather than in an <img> a generic search would find. Wix resizes
it on request, so a 640 px JPEG is asked for instead of the 2.8 MB original.
"""
import json
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
_WIX_MEDIA = 'https://static.wixstatic.com/media/'
_PICTURE_SIZE = '/v1/fit/w_640,h_640,q_85/picture.jpg'
_PICTURE_CLIMB = 14                  # parent levels searched from the dates for the section's picture


def _is_title_line(line):
    letters = re.sub(r'[^A-Za-z]', '', line)
    return len(letters) >= 3 and letters.isupper() and line != 'CALL FOR ARTISTS'


def _announcement_image(soup, run_text):
    """The picture behind the announcement: the first Wix image in the nearest section around the dates."""
    node = soup.find(string=lambda text: text and run_text in text)
    element = node.parent if node else None
    for _ in range(_PICTURE_CLIMB):
        if element is None:
            return None
        for wow in element.find_all('wow-image'):
            try:
                uri = json.loads(wow['data-image-info'])['imageData']['uri']
            except (KeyError, ValueError, TypeError):
                continue
            if uri and not re.search(r'logo|icon', (wow.find('img') or {}).get('alt', ''), re.I):
                return f'{_WIX_MEDIA}{uri}{_PICTURE_SIZE}'
        element = element.parent
    return None


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
                   description=description or None, image=_announcement_image(soup, lines[run_at])):
        logging.info("Dictée Art & Exhibition: the announced exhibition has ended; nothing current to publish.")
