from utils import fetch_and_parse
from processing import process_event
import datetime as dt
from datetime import timezone
import logging
import re
import time

LISTING_URL = 'https://www.musee-mccord-stewart.ca/en/exhibitions/'


def parse_one_date(piece):
    piece = piece.replace('\xa0', ' ').strip().strip(',').strip()
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%B %d %Y'):
        try:
            return dt.datetime.strptime(piece, fmt).date()
        except ValueError:
            pass
    return None


def parse_date_text(text):
    """Parse McCord's detail-page date string into (start, end, ongoing).

    Formats seen: 'Until <date>', 'From <date> to <date>', 'On-going', '<date>'.
    """
    if not text:
        return None, None, False
    normalized = ' '.join(text.replace('\xa0', ' ').split())
    lowered = normalized.lower()

    if 'going' in lowered or 'ongoing' in lowered:
        return None, None, True

    m = re.search(r'from\s+(.+?)\s+to\s+(.+)', normalized, re.I)
    if m:
        return parse_one_date(m.group(1)), parse_one_date(m.group(2)), False

    m = re.search(r'until\s+(.+)', normalized, re.I)
    if m:
        return None, parse_one_date(m.group(1)), False

    return parse_one_date(normalized), None, False


def scrape_mccord_stewart_exhibitions(env='prod', region='mtl'):
    """Scrape and process exhibitions from the McCord Stewart Museum."""

    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Error scraping McCord Stewart exhibitions --> no soup found")
        return

    events = soup.select('.event')
    if not events:
        logging.warning("McCord Stewart: no .event blocks found")
        return

    today = dt.datetime.now().date()

    for event in events:
        link_tag = event.find('a', href=True)
        title_tag = event.find('h1')
        if not link_tag or not title_tag:
            continue

        event_link = link_tag['href']
        event_title = title_tag.get_text(strip=True)
        subtitle_tag = event.find('h2')
        if subtitle_tag and subtitle_tag.get_text(strip=True):
            event_title = f"{event_title}: {subtitle_tag.get_text(strip=True)}"

        img_tag = event.find('img')
        image_link = img_tag['src'] if img_tag and img_tag.get('src') else None

        # Dates and full description live on the detail page
        start_date = end_date = None
        ongoing = False
        description = None
        detail = fetch_and_parse(event_link)
        time.sleep(1)
        if detail is not None:
            date_tag = detail.select_one('.date')
            start_date, end_date, ongoing = parse_date_text(
                date_tag.get_text(' ', strip=True) if date_tag else None)
            meta_desc = detail.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc['content'].strip()

        if ongoing:
            phase = 'current'
        elif end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        event_details = {
            'name': event_title,
            'venue': 'McCord Stewart Museum',
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

        # Add logging for dev environment
        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        # Process event in prod environment
        if env == 'prod':
            process_event(event_details, region)
