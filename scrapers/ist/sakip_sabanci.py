from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import json
import logging
import re
import time

from bs4 import BeautifulSoup

# The site is a Next.js app whose styled markup uses build-hashed class names,
# but every page also embeds the data it renders as JSON in __NEXT_DATA__ -
# far more stable to read than the markup.
BASE_URL = 'https://www.sakipsabancimuzesi.org'
WHATS_ON_URL = f'{BASE_URL}/en/whatson'

# 65 past exhibitions go back to 2003; only keep roughly the last two years.
PAST_WINDOW_DAYS = 730
MAX_DESCRIPTION_CHARS = 500

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# "25 June - 27 December 2026", "12 September 2025 - 8 March 2026",
# "9 June 2026 - Ongoing"
DATE_RE = re.compile(
    rf'^(?P<d1>\d{{1,2}})\s*(?P<m1>{MONTH_RE})?\s*(?P<y1>\d{{4}})?\s*[–—-]\s*'
    rf'(?:(?P<d2>\d{{1,2}})\s+(?P<m2>{MONTH_RE})\s+(?P<y2>\d{{4}})|(?P<open>Ongoing|Continues))$',
    re.IGNORECASE
)


def parse_dates(text):
    """Return (start_date, end_date, open_ended) from a card's date string."""
    text = ' '.join((text or '').replace('\xa0', ' ').split())
    match = DATE_RE.match(text)
    if not match:
        return None, None, False
    try:
        if match.group('open'):
            if not (match.group('m1') and match.group('y1')):
                return None, None, False
            start = dt.date(int(match.group('y1')), MONTH_TO_NUM_DICT[match.group('m1').lower()],
                            int(match.group('d1')))
            return start, None, True
        y2 = int(match.group('y2'))
        m2 = MONTH_TO_NUM_DICT[match.group('m2').lower()]
        end = dt.date(y2, m2, int(match.group('d2')))
        m1 = MONTH_TO_NUM_DICT[match.group('m1').lower()] if match.group('m1') else m2
        y1 = int(match.group('y1')) if match.group('y1') else y2
        start = dt.date(y1, m1, int(match.group('d1')))
        if start > end and not match.group('y1'):
            start = start.replace(year=start.year - 1)
        return start, end, False
    except ValueError:
        logging.warning(f"Sakip Sabanci: could not parse dates {text!r}")
        return None, None, False


def next_data(soup):
    tag = soup.find('script', id='__NEXT_DATA__') if soup else None
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def fetch_description(detail_url):
    """The listing cards carry no description; the detail page's JSON does."""
    data = next_data(fetch_and_parse(detail_url))
    time.sleep(0.5)
    try:
        html = data['props']['pageProps']['pageData']['data']['eventAbout']['description']
    except (KeyError, TypeError):
        return None
    text = ' '.join(BeautifulSoup(html, 'html.parser').get_text(' ', strip=True).split())
    if len(text) > MAX_DESCRIPTION_CHARS:
        text = text[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'
    return text or None


def scrape_sakip_sabanci_exhibitions(env='prod', region='ist'):
    """Scrape and process exhibitions from the Sakıp Sabancı Museum."""

    data = next_data(fetch_and_parse(WHATS_ON_URL))
    if data is None:
        logging.warning("Sakip Sabanci: could not read __NEXT_DATA__ from the what's-on page")
        return

    try:
        page_data = data['props']['pageProps']['pageData']['data']
        current_cards = [card for program in page_data['currentMuseumProgram']
                         for card in program.get('tabContent', [])]
        past_cards = page_data.get('pastExhibitionPrograms', [])
    except (KeyError, TypeError):
        logging.warning("Sakip Sabanci: unexpected __NEXT_DATA__ structure")
        return

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)
    seen_ids = set()

    for card, is_past_list in [(c, False) for c in current_cards] + [(c, True) for c in past_cards]:
        if card.get('type') != 'exhibition' or not card.get('title') or card.get('id') in seen_ids:
            continue
        seen_ids.add(card.get('id'))

        start_date, end_date, open_ended = parse_dates(card.get('date'))

        if is_past_list:
            # The site already classifies these as past; need a real end date to place them
            if not end_date or end_date < cutoff:
                continue
        elif not start_date and not end_date:
            # e.g. "Collection Exhibition" - permanent displays with no dates at all
            open_ended = True

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        ongoing = open_ended and phase == 'current'
        event_link = BASE_URL + '/en' + card['url']

        event_details = {
            'name': ' '.join(card['title'].split()),
            'venue': 'Sakıp Sabancı Museum',
            'description': fetch_description(event_link),
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if card.get('imgUrl'):
            event_details['links'].append({'link': card['imgUrl'], 'description': 'Image'})

        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        if env == 'prod':
            process_event(event_details, region)
