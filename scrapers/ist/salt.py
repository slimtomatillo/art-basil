from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re
import time

BASE_URL = 'https://saltonline.org'
PROGRAM_URL = f'{BASE_URL}/en/program'

# SALT runs separate buildings; each is its own venue so the Map link goes to
# the right one.
VENUES = ('Salt Galata', 'Salt Beyoğlu')
MAX_DESCRIPTION_CHARS = 500

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# "June 3 – September 30, 2026", "September 16, 2026 – March 14, 2027"
RANGE_RE = re.compile(
    rf'(?P<m1>{MONTH_RE})\s+(?P<d1>\d{{1,2}})(?:,\s*(?P<y1>\d{{4}}))?\s*[–—-]\s*'
    rf'(?:(?P<m2>{MONTH_RE})\s+)?(?P<d2>\d{{1,2}}),\s*(?P<y2>\d{{4}})',
    re.IGNORECASE
)


def parse_dates(text):
    match = RANGE_RE.search(text)
    if not match:
        return None, None
    try:
        y2 = int(match.group('y2'))
        end_date = dt.date(y2, MONTH_TO_NUM_DICT[(match.group('m2') or match.group('m1')).lower()],
                           int(match.group('d2')))
        y1 = int(match.group('y1')) if match.group('y1') else y2
        start_date = dt.date(y1, MONTH_TO_NUM_DICT[match.group('m1').lower()], int(match.group('d1')))
        if start_date > end_date and not match.group('y1'):
            start_date = start_date.replace(year=start_date.year - 1)
        return start_date, end_date
    except ValueError:
        logging.warning(f"SALT: could not parse dates {match.group()!r}")
        return None, None


def collect_exhibition_links(soup):
    """The program page mixes exhibitions with tours, screenings, talks and walks;
    each card's text opens with its type label, so keep only 'Exhibition'."""
    links = []
    for a in soup.find_all('a', href=re.compile(r'^/en/.+-\d+$')):
        label = a.get_text(' ', strip=True).split(' ', 1)[0]
        if label == 'Exhibition' and a['href'] not in links:
            links.append(a['href'])
    return links


def scrape_salt_exhibitions(env='prod', region='ist'):
    """Scrape and process current/upcoming exhibitions from SALT Galata and SALT Beyoğlu."""

    soup = fetch_and_parse(PROGRAM_URL)
    if soup is None:
        logging.warning("Error scraping SALT exhibitions --> no soup found")
        return

    hrefs = collect_exhibition_links(soup)
    if not hrefs:
        logging.warning("SALT: no exhibition cards found on the program page")
        return

    today = dt.datetime.now().date()

    for href in hrefs:
        event_link = BASE_URL + href
        detail = fetch_and_parse(event_link)
        time.sleep(0.5)
        if detail is None:
            continue

        h1 = detail.find('h1')
        if not h1:
            logging.warning(f"SALT: no title found at {event_link}")
            continue
        title = ' '.join(h1.get_text(' ', strip=True).split())
        # Most titles read "Exhibition: <name>"; the type is redundant on this site
        title = re.sub(r'^Exhibition:\s*', '', title)

        # The venue is followed directly by the date range, e.g.
        # "... Salt Galata June 3 – September 30, 2026 Exhibition Share"
        page_text = ' '.join(detail.get_text(' ', strip=True).split())
        venue_match = re.search(rf'({"|".join(VENUES)})\s+({MONTH_RE}[^A-Za-z]*\d)', page_text, re.IGNORECASE)
        if not venue_match:
            logging.warning(f"SALT: could not find venue/dates for {event_link}")
            continue
        venue = next(v for v in VENUES if v.lower() == venue_match.group(1).lower())
        start_date, end_date = parse_dates(page_text[venue_match.start(2):venue_match.start(2) + 60])

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        meta_desc = detail.find('meta', attrs={'name': 'description'})
        description = ' '.join(meta_desc['content'].split()) if meta_desc and meta_desc.get('content') else None
        if description and len(description) > MAX_DESCRIPTION_CHARS:
            description = description[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'

        event_details = {
            'name': title,
            'venue': venue,
            'description': description,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        # og:image is an auto-generated share card, so use the page's first real image
        first_img = next((i['src'] for i in detail.find_all('img', src=True) if i['src'].startswith('/assets/')), None)
        if first_img:
            image_url = BASE_URL + re.sub(r'width=\d+', 'width=1200', first_img)
            event_details['links'].append({'link': image_url, 'description': 'Image'})

        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        if env == 'prod':
            process_event(event_details, region)
