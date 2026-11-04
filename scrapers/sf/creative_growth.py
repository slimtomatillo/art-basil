from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

EXHIBITIONS_URL = 'https://creativegrowth.org/exhibitions'
# The page is built by JavaScript from a JSON blob in the HTML, so the show's picture is not an
# <img> in the page: it is an image block {"image": {"extension", "id", ...}, "url": <show page>}.
# Their CDN serves any image by id, scaled by a path like w_640,h_640,c_fit.
_IMAGE_BLOCK_RE = re.compile(
    r'"image":\{"extension":"(?P<ext>\w+)"[^{}]*?"id":"(?P<id>\w+)"[^{}]*\}.{0,300}?"url":"(?P<url>[^"]*)"', re.S)
_CDN = 'https://cdn.artcld.com/img/w_640,h_640,c_fit/{id}.{ext}'


def _show_page_and_image(soup, name):
    """(show page URL, picture URL) of the show on the exhibitions page: the image block that
    links to a page named after the show. (None, None) if the page has no such block."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    for script in soup.find_all('script'):
        text = script.string or ''
        for m in _IMAGE_BLOCK_RE.finditer(text):
            if slug and slug in m.group('url').lower():
                return m.group('url'), _CDN.format(id=m.group('id'), ext=m.group('ext'))
    return None, None


def scrape_creative_growth(env='prod', region='sf'):
    """Scrape and process the exhibition(s) shown on the Creative Growth exhibitions page."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Creative Growth: could not fetch the exhibitions page; existing data kept.")
        return

    # The page is a flat run of text blocks: a title (h1) directly followed by
    # its date range (h2). Only titles whose next block reads as a date range count.
    blocks = soup.select('span[data-heading="h1"], span[data-heading="h2"]')
    found = 0
    for i, block in enumerate(blocks[:-1]):
        nxt = blocks[i + 1]
        if block['data-heading'] != 'h1' or nxt['data-heading'] != 'h2':
            continue
        name = block.get_text(' ', strip=True)
        start_date, end_date = parse_date_text(nxt.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        show_page, image = _show_page_and_image(soup, name)

        event_details = {
            'name': name,
            'venue': 'Creative Growth Art Center',
            'description': None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': show_page or EXHIBITIONS_URL, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image:
            event_details['links'].append({'link': image, 'description': 'Image'})
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
        # Only the lead block is the show at the Oakland gallery; the blocks below it
        # are off-site fairs and past presentations.
        break

    if not found:
        logging.warning("Creative Growth: no exhibitions found; existing data kept.")
