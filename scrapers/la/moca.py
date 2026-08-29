import datetime as dt
from datetime import timezone
import logging

import requests

from processing import process_event

# MOCA's site is a Next.js front end backed by a public Sanity dataset. Querying
# the dataset directly is far more stable than scraping the build-hashed CSS
# class names on the rendered page.
SANITY_QUERY_URL = 'https://ianh83xv.apicdn.sanity.io/v2021-10-21/data/query/production'
EXHIBITION_URL = 'https://www.moca.org/exhibitions/'

# Pull all current + upcoming exhibitions, plus past ones from roughly the last
# two years (the dataset holds 500+ going back to the 1980s).
PAST_WINDOW_DAYS = 730

GROQ = (
    '*[_type == "exhibition" && defined(dateStart) && '
    '(dateEnd >= $cutoff || dateStart >= $today)]{'
    'title, "slug": slug.current, dateStart, dateEnd, '
    '"image": detailedMedia.image.asset->url, description'
    '} | order(dateStart desc)'
)


def portable_text_to_string(blocks):
    """Flatten Sanity portable-text blocks into a plain string."""
    if not isinstance(blocks, list):
        return None
    parts = []
    for block in blocks:
        if isinstance(block, dict) and block.get('_type') == 'block':
            parts.append(''.join(
                child.get('text', '')
                for child in block.get('children', [])
                if isinstance(child, dict)
            ))
    text = ' '.join(p.strip() for p in parts if p.strip())
    return text or None


def parse_iso_date(value):
    if not value:
        return None
    try:
        return dt.datetime.strptime(value[:10], '%Y-%m-%d').date()
    except ValueError:
        logging.warning(f"MOCA: could not parse date {value!r}")
        return None


def fetch_exhibitions():
    """Query the Sanity dataset for the exhibitions in our date window."""
    today = dt.date.today()
    params = {
        'query': GROQ,
        '$today': f'"{today.isoformat()}"',
        '$cutoff': f'"{(today - dt.timedelta(days=PAST_WINDOW_DAYS)).isoformat()}"',
    }
    try:
        response = requests.get(SANITY_QUERY_URL, params=params,
                                headers={'User-Agent': 'Your Bot 0.1'}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching MOCA exhibitions from Sanity: {e}")
        return []
    return response.json().get('result', []) or []


def scrape_moca_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from MOCA (Museum of Contemporary Art, LA)."""

    exhibitions = fetch_exhibitions()
    if not exhibitions:
        logging.warning("MOCA: no exhibitions returned")
        return

    today = dt.datetime.now().date()

    for ex in exhibitions:
        title = ex.get('title')
        slug = ex.get('slug')
        if not title:
            continue

        start_date = parse_iso_date(ex.get('dateStart'))
        end_date = parse_iso_date(ex.get('dateEnd'))

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        event_link = EXHIBITION_URL + slug if slug else None

        event_details = {
            'name': title,
            'venue': 'MOCA',
            'description': portable_text_to_string(ex.get('description')),
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}] if event_link else [],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if ex.get('image'):
            event_details['links'].append({'link': ex['image'], 'description': 'Image'})

        # Add logging for dev environment
        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        # Process event in prod environment
        if env == 'prod':
            process_event(event_details, region)
