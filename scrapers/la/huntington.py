from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import urlparse, parse_qs, unquote

BASE_URL = 'https://www.huntington.org'

# "Sept. 20, 2026" / "June 14, 2026" - abbreviated or full month name, an
# optional trailing period, and a 4-digit year. MONTH_TO_NUM_DICT has both
# forms as keys (e.g. both 'sept' and 'september').
_MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
_DATE_RANGE_RE = re.compile(
    rf'({_MONTH_RE})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\s*[–—-]\s*'
    rf'({_MONTH_RE})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})',
    re.IGNORECASE
)


def parse_date_range(text):
    """Extract (start_date, end_date) from a 'Month D, YYYY-Month D, YYYY'
    range, or (None, None) if the text doesn't look like one."""
    match = _DATE_RANGE_RE.search(text)
    if not match:
        return None, None
    m1, d1, y1, m2, d2, y2 = match.groups()
    try:
        start_date = dt.date(int(y1), MONTH_TO_NUM_DICT[m1.lower()], int(d1))
        end_date = dt.date(int(y2), MONTH_TO_NUM_DICT[m2.lower()], int(d2))
    except (ValueError, KeyError):
        return None, None
    return start_date, end_date


def real_image_url(next_image_src):
    """The Huntington serves images through Next.js's /_next/image resizing
    proxy; pull the original CMS-hosted URL out of its `url` query param
    rather than storing the resizer's own (relative) path."""
    if not next_image_src:
        return None
    query = parse_qs(urlparse(next_image_src).query)
    if 'url' in query:
        return unquote(query['url'][0])
    return next_image_src if next_image_src.startswith('http') else BASE_URL + next_image_src


def scrape_huntington(env='prod', region='la'):
    """Scrape and process exhibitions from The Huntington."""

    url = f'{BASE_URL}/exhibitions'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning("Error scraping Huntington exhibitions --> no soup found")
        return

    today = dt.date.today()

    for article in soup.find_all('article'):
        try:
            type_tag = article.find(class_=re.compile(r'event-type'))
            if type_tag and 'exhibition' not in type_tag.get_text(strip=True).lower():
                continue

            title_link = article.find('a', class_=re.compile(r'calendar-item-card__title'))
            if not title_link:
                continue
            heading = title_link.find('h3')
            event_title = heading.get_text(strip=True) if heading else title_link.get_text(strip=True)
            href = title_link.get('href')
            if not href:
                continue
            event_link = href if href.startswith('http') else BASE_URL + href

            # Items under the page's "Ongoing" heading (permanent
            # installations) have no date element at all, unlike the
            # "Temporary" exhibitions above them.
            date_tag = article.find(class_=re.compile(r'icon-text'))
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                start_date, end_date = parse_date_range(date_text)
                if not start_date and not end_date:
                    logging.warning(f"Huntington: could not parse date range {date_text!r} for {event_title!r}")
                    continue
                ongoing = False
                if end_date and end_date < today:
                    phase = 'past'
                elif start_date and start_date > today:
                    phase = 'future'
                else:
                    phase = 'current'
            else:
                start_date, end_date, ongoing, phase = None, None, True, 'current'

            summary_tag = article.find(class_=re.compile(r'calendar-item-card__summary'))
            description = summary_tag.get_text(strip=True) if summary_tag else None

            img_tag = article.find('img')
            image_link = real_image_url(img_tag.get('src')) if img_tag else None

            event_details = {
                'name': event_title,
                'venue': 'Huntington',
                'description': description,
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
            logging.error(f"Error processing Huntington exhibition: {e}", exc_info=True)
