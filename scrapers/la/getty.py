from utils import fetch_and_parse
from processing import process_event
import datetime as dt
from datetime import timezone
import json
import logging
import time

LISTING_URL = 'https://www.getty.edu/exhibitions/'


def parse_iso_date(date_string):
    """Parse an ISO 'YYYY-MM-DD' date string to a dt.date, or None."""
    if not date_string:
        return None
    try:
        return dt.datetime.strptime(date_string[:10], '%Y-%m-%d').date()
    except ValueError:
        logging.warning(f"Getty: could not parse date {date_string!r}")
        return None


def extract_exhibition_events(soup):
    """Pull ExhibitionEvent entries out of the page's ld+json metadata.

    The Getty listing is rendered client-side, but the server embeds the full
    current + upcoming list as schema.org ExhibitionEvent objects in a
    <script type="application/ld+json"> block.
    """
    events = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or script.text)
        except (ValueError, TypeError):
            continue
        main_entity = data.get('mainEntity')
        if not isinstance(main_entity, list):
            continue
        for block in main_entity:
            for item in block.get('itemListElement', []):
                if item.get('@type') == 'ExhibitionEvent':
                    events.append(item)
    return events


def scrape_detail_page(url):
    """Fetch an exhibition page for its image and fuller title / description."""
    soup = fetch_and_parse(url)
    if soup is None:
        return {}
    detail = {}
    for prop, key in (('og:image', 'image'), ('og:title', 'title'), ('og:description', 'description')):
        tag = soup.find('meta', property=prop)
        if tag and tag.get('content'):
            detail[key] = tag['content'].replace('\xa0', ' ').strip()
    # Getty's og:title ends with a "| <section>" label ("Getty Exhibitions",
    # "Collection Highlights", ...) - drop that trailing segment.
    title = detail.get('title')
    if title and '|' in title:
        detail['title'] = title.rsplit('|', 1)[0].strip()
    return detail


def scrape_getty_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from the Getty (Center and Villa)."""

    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Error scraping Getty exhibitions --> no soup found")
        return

    events = extract_exhibition_events(soup)
    if not events:
        logging.warning("Getty: no ExhibitionEvent entries found in page metadata")
        return

    today = dt.datetime.now().date()

    for ev in events:
        event_link = ev.get('url')
        start_date = parse_iso_date(ev.get('startDate'))
        end_date = parse_iso_date(ev.get('endDate'))

        # The listing only carries current + upcoming, so derive the phase
        if start_date and start_date > today:
            phase = 'future'
        elif end_date and end_date < today:
            phase = 'past'
        else:
            phase = 'current'

        detail = scrape_detail_page(event_link) if event_link else {}
        # Be polite between detail-page requests
        time.sleep(1)

        event_title = detail.get('title') or ev.get('name')
        description = detail.get('description') or ev.get('description') or ev.get('about')

        event_details = {
            'name': event_title,
            'venue': 'Getty',
            'description': description,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}] if event_link else [],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        if detail.get('image'):
            event_details['links'].append({'link': detail['image'], 'description': 'Image'})

        # Add logging for dev environment
        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        # Process event in prod environment
        if env == 'prod':
            process_event(event_details, region)
