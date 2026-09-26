from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re
import time

BASE_URL = 'https://www.istanbulmodern.org'
SECTIONS = {'current': 'current', 'upcoming': 'future', 'past': 'past'}
NON_EXHIBITION_SLUGS = {'current', 'upcoming', 'past', 'virtual-tour', 'exhibitions'}

# The past section goes back several years; only keep roughly the last two.
PAST_WINDOW_DAYS = 730
MAX_DESCRIPTION_CHARS = 500

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# "November 5, 2026–May 23, 2027", "January 22–November 22, 2026", "March 21–December 12, 2025"
RANGE_RE = re.compile(
    rf'^(?P<m1>{MONTH_RE})\s+(?P<d1>\d{{1,2}})(?:,\s*(?P<y1>\d{{4}}))?\s*[–—-]\s*'
    rf'(?:(?P<m2>{MONTH_RE})\s+)?(?P<d2>\d{{1,2}}),\s*(?P<y2>\d{{4}})$',
    re.IGNORECASE
)
# "September 8, 2026" - an opening date with no closing date (long-running shows)
SINGLE_RE = re.compile(
    rf'^(?P<m>{MONTH_RE})\s+(?P<d>\d{{1,2}}),\s*(?P<y>\d{{4}})$',
    re.IGNORECASE
)


def parse_dates(text):
    """Return (start_date, end_date) from the date line under an exhibition's title."""
    text = ' '.join(text.replace('\xa0', ' ').split())
    try:
        match = RANGE_RE.match(text)
        if match:
            y2 = int(match.group('y2'))
            end_date = dt.date(y2, MONTH_TO_NUM_DICT[(match.group('m2') or match.group('m1')).lower()],
                               int(match.group('d2')))
            y1 = int(match.group('y1')) if match.group('y1') else y2
            start_date = dt.date(y1, MONTH_TO_NUM_DICT[match.group('m1').lower()], int(match.group('d1')))
            # "December 20–January 10, 2027" - no explicit start year, so it began the year before
            if start_date > end_date and not match.group('y1'):
                start_date = start_date.replace(year=start_date.year - 1)
            return start_date, end_date
        match = SINGLE_RE.match(text)
        if match:
            return dt.date(int(match.group('y')), MONTH_TO_NUM_DICT[match.group('m').lower()],
                           int(match.group('d'))), None
    except ValueError:
        pass
    logging.warning(f"Istanbul Modern: could not parse dates {text!r}")
    return None, None


def collect_exhibition_links():
    """Return [(href, section_phase)] across the current/upcoming/past listings, deduped."""
    found = {}
    for section, section_phase in SECTIONS.items():
        soup = fetch_and_parse(f'{BASE_URL}/en/exhibitions/{section}')
        if soup is None:
            logging.warning(f"Istanbul Modern: could not fetch the {section} exhibitions listing")
            continue
        for a in soup.select('a[href^="/en/exhibitions/"]'):
            href = a['href'].split('?')[0].rstrip('/')
            if href.split('/')[-1] in NON_EXHIBITION_SLUGS or href in found:
                continue
            found[href] = section_phase
    return list(found.items())


def scrape_istanbul_modern_exhibitions(env='prod', region='ist'):
    """Scrape and process exhibitions from Istanbul Modern."""

    links = collect_exhibition_links()
    if not links:
        logging.warning("Istanbul Modern: no exhibitions found")
        return

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)

    for href, section_phase in links:
        event_link = BASE_URL + href
        soup = fetch_and_parse(event_link)
        time.sleep(0.5)
        if soup is None:
            continue

        title_tag = soup.find('h1')
        if not title_tag or not title_tag.get_text(strip=True):
            logging.warning(f"Istanbul Modern: no title found at {event_link}")
            continue
        event_title = ' '.join(title_tag.get_text(' ', strip=True).split())

        date_tag = soup.select_one('ul.breadcrumb ~ div.pl-3')
        start_date, end_date = parse_dates(date_tag.get_text(strip=True)) if date_tag else (None, None)

        if end_date and end_date < today:
            if end_date < cutoff:
                continue
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        elif start_date or end_date:
            phase = 'current'
        else:
            phase = section_phase

        # A lone opening date (no closing date) marks a long-running show
        ongoing = bool(start_date and not end_date and start_date <= today)

        paragraph = title_tag.parent.find('p')
        description = ' '.join(paragraph.get_text(' ', strip=True).split()) if paragraph else None
        if description and len(description) > MAX_DESCRIPTION_CHARS:
            description = description[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'

        event_details = {
            'name': event_title,
            'venue': 'Istanbul Modern',
            'description': description,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            event_details['links'].append({'link': og_image['content'], 'description': 'Image'})

        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        if env == 'prod':
            process_event(event_details, region)
