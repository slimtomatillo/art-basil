from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://ago.ca'

_MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
_SINGLE_DATE_RE = re.compile(rf'({_MONTH_RE})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})', re.IGNORECASE)

_ONGOING_LABELS = {'on now', 'on view'}


def parse_single_date(text):
    """Best-effort parse of a 'Month D, YYYY' fragment anywhere in text."""
    match = _SINGLE_DATE_RE.search(text)
    if not match:
        return None
    month, day, year = match.groups()
    try:
        return dt.date(int(year), MONTH_TO_NUM_DICT[month.lower()], int(day))
    except (ValueError, KeyError):
        return None


def parse_date_text(text):
    """AGO's date line comes in one of four shapes: a bare 'On now'/'On
    view' (ongoing, no date), 'On now until <date>' (current, known end
    date), 'Opens <date>' (future, known start date), or something else we
    don't recognize. Returns (start_date, end_date, ongoing)."""
    normalized = ' '.join(text.split())
    lowered = normalized.lower()

    if lowered in _ONGOING_LABELS:
        return None, None, True

    if lowered.startswith('on now until'):
        end_date = parse_single_date(normalized)
        return None, end_date, False

    if lowered.startswith('opens'):
        start_date = parse_single_date(normalized)
        return start_date, None, False

    return None, None, False


def scrape_ago(env='prod', region='tor'):
    """Scrape and process exhibitions from the Art Gallery of Ontario."""

    url = f'{BASE_URL}/exhibitions'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning("Error scraping AGO exhibitions --> no soup found")
        return

    today = dt.date.today()

    for article in soup.find_all('article', class_=re.compile(r'node--type-agoc-exhibition')):
        try:
            title_tag = article.find(['h2', 'h3'])
            title_link = title_tag.find('a') if title_tag else None
            if not title_link:
                continue
            # Separator needed: a subtitle (e.g. "...from the Dallas Museum
            # of Art") sits in its own <span> right after the main title
            # with no space in the markup between them.
            event_title = ' '.join(title_link.get_text(' ', strip=True).split())
            href = title_link.get('href')
            if not href:
                continue
            event_link = href if href.startswith('http') else BASE_URL + href

            date_tag = article.find(class_='field--name-field-date-time-description')
            date_text = date_tag.get_text(strip=True) if date_tag else ''
            start_date, end_date, ongoing = parse_date_text(date_text)

            if not start_date and not end_date and not ongoing:
                logging.warning(f"AGO: could not parse date text {date_text!r} for {event_title!r}")
                continue

            if ongoing:
                phase = 'current'
            elif end_date and end_date < today:
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            else:
                phase = 'current'

            img_tag = article.find('img')
            image_link = None
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                image_link = src if src.startswith('http') else BASE_URL + src

            event_details = {
                'name': event_title,
                'venue': 'AGO',
                'description': None,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'dev':
                logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")

            if env == 'prod':
                process_event(event_details, region)

        except Exception as e:
            logging.error(f"Error processing AGO exhibition: {e}", exc_info=True)
