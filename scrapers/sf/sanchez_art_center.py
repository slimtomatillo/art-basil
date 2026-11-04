from utils import fetch_and_parse
from images import secure_image_url
from urllib.parse import urljoin
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

# The site is a hand-edited static page that only answers on plain http (the
# https handshake is reset), so the calendar is fetched over http.
CALENDAR_URL = 'http://sanchezartcenter.org/Calendar.htm'

# The year's calendar is a table of rows: date label | title and details. A row
# is an exhibition when its title says so; everything else (a talk, a popup,
# the winter art faire) is tagged 'event'.
_EXHIBITION_RE = re.compile(r'\b(show|exhibition|exhibit)\b', re.I)
_MAX_DESCRIPTION = 400

# The calendar has no pictures, but the site keeps a show's pictures in a year folder
# (images/2026/...): the Exhibitions page has the current members show's, and a show with its
# own page (the winter art faire) has its poster there. Header, mural and badge pictures
# elsewhere on the page are the site's own and are not used.
EXHIBITIONS_URL = 'http://sanchezartcenter.org/EXHIBITIONS.html'
_YEAR_FOLDER_RE = re.compile(r'(?:^|/)images/20\d\d/', re.I)
_PHOTO_RE = re.compile(r'\.(?:jpe?g|png)$', re.I)       # the .gif files there are title banners
_ORDINAL_RE = re.compile(r'\d+(?:st|nd|rd|th) annual', re.I)


def _year_folder_pictures(soup, base_url):
    return [urljoin(base_url, i['src']) for i in soup.find_all('img', src=True) if _YEAR_FOLDER_RE.search(i['src'])]


def _exhibition_photo(exhibitions, name):
    """The first photo on the Exhibitions page, when that page is about the show `name` (matched by
    its "68th Annual" style number)."""
    key = _ORDINAL_RE.search(name)
    if exhibitions is None or not key or key.group(0).lower() not in exhibitions.get_text(' ').lower():
        return None
    return next((u for u in _year_folder_pictures(exhibitions, EXHIBITIONS_URL) if _PHOTO_RE.search(u)), None)


def _own_page_poster(url):
    soup = fetch_and_parse(url)
    return next(iter(_year_folder_pictures(soup, url)), None) if soup is not None else None


def scrape_sanchez_art_center(env='prod', region='sf'):
    """Scrape and process the exhibitions and events on the Sanchez Art Center calendar."""

    today = region_today(region)
    soup = fetch_and_parse(CALENDAR_URL)
    if soup is None:
        logging.warning("Sanchez Art Center: could not fetch the calendar page; existing data kept.")
        return

    exhibitions = fetch_and_parse(EXHIBITIONS_URL)
    for row in soup.find_all('tr'):
        cells = row.find_all('td', recursive=False)
        # Date label and details are the two cells that hold text
        texts = [c for c in cells if c.get_text(strip=True)]
        if len(texts) != 2:
            continue
        date_text = texts[0].get_text(' ', strip=True)
        start_date, end_date = parse_date_text(date_text, today)
        if not start_date:
            continue
        end_date = end_date or start_date

        lines = [l.replace('\xa0', ' ').strip() for l in texts[1].get_text('\n').split('\n')]
        lines = [l for l in lines if l]
        if not lines:
            continue
        # A title can be wrapped by a hand-placed <br> after a comma
        title_end = 1
        while lines[title_end - 1].endswith(',') and title_end < len(lines):
            title_end += 1
        name = ' '.join(lines[:title_end]).rstrip(',')
        description = ' '.join(lines[title_end:])[:_MAX_DESCRIPTION] or None

        kind = 'exhibition' if _EXHIBITION_RE.search(name) else 'event'
        phase = derive_phase(start_date, end_date, today) or 'current'

        link_tag = texts[1].find('a', href=True)
        event_link = CALENDAR_URL
        image = _exhibition_photo(exhibitions, name) if phase != 'past' else None
        if link_tag and not link_tag['href'].startswith(('http', 'mailto')):
            event_link = 'http://sanchezartcenter.org/' + link_tag['href']
            if phase != 'past':
                image = _own_page_poster(event_link) or image

        event_details = {
            'name': name,
            'venue': 'Sanchez Art Center',
            'description': description,
            'tags': [kind] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}]
                     + ([{'link': secure_image_url(image), 'description': 'Image'}] if image else []),
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        if env == 'dev':
            logging.info(f"Event found: {name} ({kind}, {phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
