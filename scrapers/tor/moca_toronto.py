import datetime as dt
from datetime import timezone
import logging
import re

import requests
from bs4 import BeautifulSoup

from utils import fetch_and_parse
from processing import process_event

LISTING_URL = 'https://moca.ca/exhibitions/'
REST_URL = 'https://moca.ca/wp-json/wp/v2/exhibitions?per_page=100'

_DATE_RE = re.compile(
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},\s*\d{4})'
)


def parse_long_date(text):
    try:
        return dt.datetime.strptime(' '.join(text.split()), '%B %d, %Y').date()
    except ValueError:
        logging.warning(f"MOCA Toronto: could not parse date {text!r}")
        return None


def fetch_rest_meta():
    """Map slug -> {'title', 'description'} from the WP REST API (clean text)."""
    meta = {}
    try:
        response = requests.get(REST_URL, headers={'User-Agent': 'Your Bot 0.1'}, timeout=30)
        response.raise_for_status()
        for item in response.json():
            slug = item.get('slug')
            if not slug:
                continue
            title = BeautifulSoup(item.get('title', {}).get('rendered', ''), 'html.parser').get_text(strip=True)
            excerpt = BeautifulSoup(item.get('excerpt', {}).get('rendered', ''), 'html.parser').get_text(' ', strip=True)
            meta[slug] = {'title': title or None, 'description': excerpt or None}
    except (requests.RequestException, ValueError) as e:
        logging.warning(f"MOCA Toronto: REST metadata fetch failed ({e}); falling back to listing text")
    return meta


def scrape_moca_toronto_exhibitions(env='prod', region='tor'):
    """Scrape and process exhibitions from MOCA Toronto (Museum of Contemporary Art)."""

    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Error scraping MOCA Toronto exhibitions --> no soup found")
        return

    items = soup.select('.jet-listing-grid__item')
    if not items:
        logging.warning("MOCA Toronto: no .jet-listing-grid__item blocks found")
        return

    rest_meta = fetch_rest_meta()
    today = dt.datetime.now().date()

    for item in items:
        link_tag = item.find('a', href=True)
        if not link_tag:
            continue
        event_link = link_tag['href']
        slug = event_link.rstrip('/').split('/')[-1]

        found = _DATE_RE.findall(item.get_text(' ', strip=True))
        start_date = parse_long_date(found[0]) if found else None
        end_date = parse_long_date(found[1]) if len(found) > 1 else None

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        meta = rest_meta.get(slug, {})
        event_title = meta.get('title')
        if not event_title:
            # Listing text is "[status] <start> — <end> <artist> <title>"; take what's after the dates
            tail = _DATE_RE.sub('', item.get_text(' ', strip=True)).replace('—', ' ')
            event_title = ' '.join(tail.split()).lstrip('Upcoming').strip() or slug.replace('-', ' ').title()

        img_tag = item.find('img')
        image_link = None
        if img_tag:
            image_link = img_tag.get('src') or img_tag.get('data-src')

        event_details = {
            'name': event_title,
            'venue': 'MOCA Toronto',
            'description': meta.get('description'),
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
