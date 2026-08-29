import datetime as dt
from datetime import timezone
import json
import logging
import re

from utils import fetch_and_parse
from processing import process_event

LISTING_URL = 'https://www.thepowerplant.org/whats-on/exhibitions'
EXHIBITION_URL = 'https://www.thepowerplant.org/whats-on/exhibitions/'


def parse_iso_date(value):
    if not value:
        return None
    try:
        return dt.datetime.strptime(value[:10], '%Y-%m-%d').date()
    except ValueError:
        logging.warning(f"Power Plant: could not parse date {value!r}")
        return None


def first_text_block(body):
    """Pull the first 'layouts.text' block's text out of a Strapi body list."""
    if not isinstance(body, list):
        return None
    for block in body:
        if isinstance(block, dict) and block.get('__component') == 'layouts.text' and block.get('text'):
            text = re.sub(r'<[^>]+>', '', block['text'])
            text = ' '.join(text.split())
            if text:
                return text
    return None


def scrape_power_plant_exhibitions(env='prod', region='tor'):
    """Scrape and process exhibitions from The Power Plant Contemporary Art Gallery."""

    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Error scraping The Power Plant exhibitions --> no soup found")
        return

    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    if next_data_tag is None:
        logging.warning("The Power Plant: __NEXT_DATA__ not found")
        return

    try:
        page_props = json.loads(next_data_tag.string or next_data_tag.text)['props']['pageProps']
    except (ValueError, KeyError, TypeError) as e:
        logging.warning(f"The Power Plant: could not parse __NEXT_DATA__: {e}")
        return

    entries = []
    for key in ('currentExhibitions', 'upcomingExhibitions', 'pastExhibitions'):
        entries.extend(page_props.get(key) or [])

    if not entries:
        logging.warning("The Power Plant: no exhibitions in page data")
        return

    today = dt.datetime.now().date()
    seen_slugs = set()

    for entry in entries:
        attrs = entry.get('attributes', entry)
        slug = attrs.get('slug')
        title = attrs.get('title') or attrs.get('card_title')
        if not title or (slug and slug in seen_slugs):
            continue
        if slug:
            seen_slugs.add(slug)

        start_date = parse_iso_date(attrs.get('start_date'))
        end_date = parse_iso_date(attrs.get('end_date'))

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        description = attrs.get('summary') or first_text_block(attrs.get('body'))

        image_link = None
        cover = (attrs.get('cover_image') or {}).get('data')
        if isinstance(cover, dict):
            image_link = (cover.get('attributes') or {}).get('url')

        event_link = EXHIBITION_URL + slug if slug else None

        event_details = {
            'name': title,
            'venue': 'The Power Plant',
            'description': description,
            'tags': ['exhibition', phase, 'gallery'],
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
