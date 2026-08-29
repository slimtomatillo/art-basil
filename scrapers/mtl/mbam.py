from utils import fetch_and_parse
from processing import process_event
import calendar
import datetime as dt
from datetime import timezone
import logging
import re
import time

BASE_URL = 'https://www.mbam.qc.ca'
LISTING_URL = 'https://www.mbam.qc.ca/en/exhibitions/'

# The listing goes back years; only keep past exhibitions from roughly the last
# two years.
PAST_WINDOW_DAYS = 730

_MONTH_FORMATS = ('%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%B %d', '%b %d')


def parse_one_date(piece, fallback_year=None, is_end=False):
    piece = piece.replace('\xa0', ' ').strip().strip(',').strip()
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
        day = parsed.day if '%d' in fmt else (
            calendar.monthrange(year, parsed.month)[1] if is_end else 1)
        return dt.date(year, parsed.month, day)
    return None


def parse_date_range(text):
    if not text:
        return None, None
    normalized = ' '.join(text.replace('\xa0', ' ').split())
    parts = re.split(r'\s*[–—-]\s*', normalized)
    if len(parts) == 1:
        return parse_one_date(parts[0]), None
    end_date = parse_one_date(parts[-1], is_end=True)
    year = end_date.year if end_date else None
    start_date = parse_one_date(parts[0], fallback_year=year)
    return start_date, end_date


def absolute_url(href):
    if not href:
        return None
    return href if href.startswith('http') else BASE_URL + href


def scrape_from_detail_page(url):
    """For 'coming soon' cards that render no text: use the detail page's
    Open Graph tags and the first date in the body."""
    soup = fetch_and_parse(url)
    if soup is None:
        return None

    def og(prop):
        tag = soup.find('meta', property=prop)
        return tag['content'].strip() if tag and tag.get('content') else None

    title = og('og:title')
    if title:
        title = title.split('|')[0].strip()
    body_text = soup.get_text(' ', strip=True)
    # A "coming soon" show opens in the current year or later; ignore stray
    # artwork dates ("February 4, 1850") elsewhere on the page.
    this_year = dt.date.today().year
    start_date = None
    for candidate in re.findall(
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+\d{1,2},\s*\d{4}', body_text):
        parsed = parse_one_date(candidate)
        if parsed and this_year <= parsed.year <= this_year + 3:
            start_date = parsed
            break
    return {
        'title': title,
        'description': og('og:description'),
        'image': og('og:image'),
        'start_date': start_date,
        'end_date': None,
    }


def scrape_mbam_exhibitions(env='prod', region='mtl'):
    """Scrape and process exhibitions from the Montreal Museum of Fine Arts (MBAM/MMFA)."""

    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Error scraping MBAM exhibitions --> no soup found")
        return

    cards = soup.select('a.target.block[href]')
    if not cards:
        logging.warning("MBAM: no exhibition cards found")
        return

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)
    seen_links = set()

    for card in cards:
        href = card['href']
        if '/exhibition' not in href:
            continue
        event_link = absolute_url(href)
        if event_link in seen_links:
            continue
        seen_links.add(event_link)

        title_tag = card.find(['h2', 'h3'])
        date_tag = card.select_one('.big-sup')

        if title_tag and title_tag.get_text(strip=True):
            event_title = title_tag.get_text(strip=True)
            start_date, end_date = parse_date_range(
                date_tag.get_text(' ', strip=True) if date_tag else None)
            img_tag = card.find('img')
            image_link = img_tag['src'] if img_tag and img_tag.get('src') else None
            description = None
        else:
            # Text-less "coming soon" card - fall back to the detail page
            detail = scrape_from_detail_page(event_link)
            time.sleep(1)
            if not detail or not detail['title']:
                continue
            event_title = detail['title']
            start_date, end_date = detail['start_date'], detail['end_date']
            image_link = detail['image']
            description = detail['description']

        if end_date and end_date < today:
            if end_date < cutoff:
                continue  # too old to bother listing
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        event_details = {
            'name': event_title,
            'venue': 'Montreal Museum of Fine Arts',
            'description': description,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        # Add logging for dev environment
        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        # Process event in prod environment
        if env == 'prod':
            process_event(event_details, region)
