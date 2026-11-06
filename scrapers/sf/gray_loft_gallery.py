"""Gray Loft Gallery (2889 Ford St, Jingletown, Oakland), an alternative art gallery.

The home page's "Current Exhibit" block is a Squarespace text block: the run as a heading
("September 26 - November 14, 2026"), the receptions, then a paragraph that introduces the show with
its title in bold italics ("We are delighted to present <em>Gestures of Willful Abandon,</em> an
exhibit that..."). The Upcoming Events page is rarely updated and is not read.
"""
import logging
import re

from utils import fetch_and_parse
from date_parsing import parse_date_text
from images import PageText, image_in_card
from processing import region_today
from scrapers.tor._common import publish

HOME_URL = 'https://www.grayloftgallery.com/'
VENUE = 'Gray Loft Gallery'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')
_MAX_DESCRIPTION = 400


def scrape_gray_loft_gallery(env='prod', region='sf'):
    """Scrape and process the exhibit now on view at Gray Loft Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("Gray Loft Gallery: could not fetch the home page; existing data kept.")
        return
    heading = next((h for h in soup.find_all(['h2', 'h3'])
                    if _RANGE_RE.match(' '.join(h.get_text(' ').split()))), None)
    block = heading.parent if heading is not None else None
    title_tag = block.find('em') if block is not None else None
    if title_tag is None:
        logging.warning("Gray Loft Gallery: no current exhibit with dates and a title found; existing data kept.")
        return
    title = ' '.join(title_tag.get_text(' ').split()).strip(' ,.')
    start_date, end_date = parse_date_text(' '.join(heading.get_text(' ').split()), today)
    paragraphs = [' '.join(p.get_text(' ').split()) for p in block.find_all('p')]
    intro = next((p for p in paragraphs if title in p), '')
    description = intro[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(intro) > _MAX_DESCRIPTION else intro
    image = image_in_card(PageText(soup), title, HOME_URL, [title], check_size=False)
    if not publish(env, region, VENUE, title, start_date, end_date, HOME_URL, tag='gallery',
                   description=description or None, image=image):
        logging.info("Gray Loft Gallery: the exhibit on the home page has ended; nothing current to publish.")
