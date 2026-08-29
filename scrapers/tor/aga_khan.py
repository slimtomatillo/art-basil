from utils import fetch_and_parse
from processing import process_event
import calendar
import datetime as dt
from datetime import timezone
import logging
import re

LISTING_URLS = [
    'https://agakhanmuseum.org/whats-on/',
    'https://agakhanmuseum.org/past-exhibitions/',
]

_MONTH_FORMATS = ('%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y',
                  '%B %d', '%b %d', '%B %Y', '%b %Y')


def parse_one_date(piece, fallback_year=None, is_end=False):
    """Parse a single date fragment. Fills in a missing year from fallback_year
    and a missing day with the 1st (start) or last day of month (end)."""
    piece = piece.strip().strip(',').strip()
    if not piece:
        return None
    for fmt in _MONTH_FORMATS:
        try:
            parsed = dt.datetime.strptime(piece, fmt)
        except ValueError:
            continue
        year = parsed.year if '%Y' in fmt else fallback_year
        if not year:
            return None
        if '%d' in fmt:
            day = parsed.day
        else:
            day = calendar.monthrange(year, parsed.month)[1] if is_end else 1
        return dt.date(year, parsed.month, day)
    return None


def parse_date_range(text):
    """Parse 'Month D, YYYY - Month D, YYYY' style strings (many spacing and
    abbreviation variants) into (start_date, end_date)."""
    if not text:
        return None, None
    normalized = ' '.join(text.split())
    parts = re.split(r'\s*[–—-]\s*', normalized)
    if len(parts) == 1:
        return parse_one_date(parts[0]), None

    end_date = parse_one_date(parts[-1], is_end=True)
    year = end_date.year if end_date else None
    start_date = parse_one_date(parts[0], fallback_year=year)
    if start_date is None:
        # try again borrowing the whole trailing fragment's year token
        year_match = re.search(r'(\d{4})', parts[-1])
        if year_match:
            start_date = parse_one_date(parts[0], fallback_year=int(year_match.group(1)))
    if start_date is None and end_date is None:
        logging.warning(f"Aga Khan: could not parse date range {text!r}")
    return start_date, end_date


def largest_image(img_tag):
    """Return a full-size image URL from a lazyload <img>, stripping resize params."""
    if not img_tag:
        return None
    srcset = img_tag.get('data-srcset') or img_tag.get('srcset') or ''
    candidate = None
    if srcset:
        candidate = srcset.split(',')[-1].strip().split(' ')[0]
    candidate = candidate or img_tag.get('data-lazyload') or img_tag.get('src')
    if candidate and '?' in candidate:
        candidate = candidate.split('?')[0]
    return candidate or None


def scrape_aga_khan_exhibitions(env='prod', region='tor'):
    """Scrape and process exhibitions from the Aga Khan Museum."""

    today = dt.datetime.now().date()
    seen_links = set()

    for url in LISTING_URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping Aga Khan exhibitions ({url}) --> no soup found")
            continue

        cards = [c for c in soup.select('.c-event-card')
                 if 'c-event-card--exhibition' in c.get('class', [])]
        if not cards:
            logging.warning(f"Aga Khan: no exhibition cards found at {url}")
            continue

        for card in cards:
            title_tag = card.select_one('.c-event-card__title')
            event_title = title_tag.get_text(' ', strip=True) if title_tag else None
            if not event_title:
                continue

            link_tag = card.select_one('.c-event-card__link[href]')
            event_link = link_tag['href'] if link_tag else None
            if event_link and event_link in seen_links:
                continue
            if event_link:
                seen_links.add(event_link)

            dates_tag = card.select_one('.c-event-card__dates')
            start_date, end_date = parse_date_range(dates_tag.get_text(' ', strip=True) if dates_tag else None)

            if end_date and end_date < today:
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            else:
                phase = 'current'

            image_link = largest_image(card.select_one('img'))

            event_details = {
                'name': event_title,
                'venue': 'Aga Khan Museum',
                'description': None,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': event_link, 'description': 'Event Page'}] if event_link else [],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            # Add logging for dev environment
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)
