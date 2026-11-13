from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

SITE = 'https://www.paloalto.gov'
BASE_URL = SITE + '/Departments/Community-Services/Arts-Sciences/Palo-Alto-Art-Center/See-Art/Exhibitions'

# Past is one long accordion of every show since the 1970s; only the most
# recent are worth re-scraping daily.
MAX_PAST = 12

_DATE_RANGE_RE = re.compile(r'[A-Z][a-z]+\.? \d{1,2}(?:, \d{4})?\s*[-–]\s*(?:[A-Z][a-z]+\.? )?\d{1,2}, \d{4}')
# The page's paragraphs include picture credits and captions among the text ("Left image: Nathan Oliveira, Profile,
# 2010, oil on canvas, 66 x 50 in., Courtesy of ..."); they are not the show's description
_CAPTION_RE = re.compile(r'^(?:(?:left|right|top|bottom)\s+)?image\b|courtesy of|\bphoto(?:graph)? by\b|\b\d+(?:\.\d+)?\s*[x×]\s*\d+|,\s*(?:19|20)\d\d,', re.IGNORECASE)
_MAX_DESCRIPTION = 500

def absolute(src):
    return SITE + src if src.startswith('/') else src

def description_after(start):
    """The show's text: the first paragraphs after `start` (its heading or dates), up to the next heading, leaving out
    the date line and picture captions, in plain text of at most 500 characters cut at a sentence end ("" if none)."""
    parts = []
    for tag in start.find_all_next(['p', 'h2']):
        if tag.name == 'h2':
            break
        text = ' '.join(tag.get_text(' ', strip=True).split())
        if len(text) < 40 or _DATE_RANGE_RE.match(text) or _CAPTION_RE.search(text):
            continue
        parts.append(text)
        if sum(len(part) for part in parts) >= 200:
            break
    text = ' '.join(parts)
    if len(text) > _MAX_DESCRIPTION:
        cut = text[:_MAX_DESCRIPTION]
        sentence_end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
        text = cut[:sentence_end + 1] if sentence_end > 200 else cut.rsplit(' ', 1)[0]
    return text


def first_image(main):
    img = main.find('img', src=True)
    return absolute(img['src']) if img else None

def scrape_palo_alto_art_center(env='prod', region='sf'):
    """Scrape and process exhibitions from the Palo Alto Art Center."""

    today = region_today(region)

    def emit(name, start_date, end_date, url, tab_phase, image_link=None, description=None):
        phase = derive_phase(start_date, end_date, today) or tab_phase
        event_details = {
            'name': name,
            'venue': 'Palo Alto Art Center',
            'description': description,
            'tags': ['exhibition'] + [phase] + ['museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': url, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    def get_main(path):
        url = f'{BASE_URL}/{path}'
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Palo Alto Art Center: could not fetch {url}; existing data kept.")
            return url, None
        return url, soup.find(id='main-content') or soup

    # Current: a single show - title is the page heading, dates lead the body
    url, main = get_main('Current-Exhibition')
    if main:
        title = main.find('h1')
        m = _DATE_RANGE_RE.search(main.get_text(' ', strip=True))
        if title and m:
            start_date, end_date = parse_date_text(m.group(0), today)
            emit(title.get_text(' ', strip=True), start_date, end_date, url, 'current', first_image(main),
                 description=description_after(title) or None)
        else:
            logging.warning("Palo Alto Art Center: no current exhibition found")

    # Upcoming: each show is an <h2> title followed by an <h3> date range
    url, main = get_main('Upcoming')
    if main:
        for h2 in main.find_all('h2'):
            date_tag = h2.find_next('h3')
            start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today) if date_tag else (None, None)
            if not (start_date or end_date):
                continue
            emit(h2.get_text(' ', strip=True), start_date, end_date, url, 'future', first_image(main),
                 description=description_after(date_tag) or None)

    # Past: accordion of <h2> "Title | dates" (or a bare title with the dates in an <h4>)
    url, main = get_main('Past-Exhibitions')
    if main:
        count = 0
        for h2 in main.find_all('h2'):
            heading = h2.get_text(' ', strip=True)
            # Dates are tacked onto the heading after a separator that varies
            # ("|", or a lowercase L standing in for one); otherwise they sit in an <h4>.
            m = _DATE_RANGE_RE.search(heading)
            if m:
                date_text = m.group(0)
                name = re.sub(r'(?:\s+l|\s*\|)?\s*$', '', heading[:m.start()]).strip()
            else:
                h4 = h2.find_next('h4')
                date_text = h4.get_text(' ', strip=True) if h4 else ''
                name = heading
            start_date, end_date = parse_date_text(date_text, today)
            if not (start_date or end_date):
                continue
            emit(name, start_date, end_date, url, 'past')
            count += 1
            if count >= MAX_PAST:
                break
