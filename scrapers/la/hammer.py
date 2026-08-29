from utils import fetch_and_parse
from processing import process_event
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://hammer.ucla.edu'
LISTING_URLS = [
    'https://hammer.ucla.edu/exhibitions/on-view',
    'https://hammer.ucla.edu/exhibitions/upcoming',
    'https://hammer.ucla.edu/exhibitions/all',
]


def parse_iso_date(value):
    """Parse an ISO datetime string ('2026-04-05T00:00:00Z') to a dt.date."""
    if not value:
        return None
    try:
        return dt.datetime.strptime(value[:10], '%Y-%m-%d').date()
    except ValueError:
        logging.warning(f"Hammer: could not parse date {value!r}")
        return None


def absolute_url(href):
    if not href:
        return None
    return href if href.startswith('http') else BASE_URL + href


def scrape_hammer_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from the Hammer Museum."""

    today = dt.datetime.now().date()
    seen_links = set()

    for url in LISTING_URLS:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping Hammer exhibitions ({url}) --> no soup found")
            continue

        articles = soup.select('article.node--type-exhibition')
        if not articles:
            logging.warning(f"Hammer: no exhibition articles found at {url}")
            continue

        for article in articles:
            title_tag = article.select_one('.page-teaser__title, .result-item__title')
            event_title = title_tag.get_text(strip=True) if title_tag else None
            if not event_title:
                continue

            event_link = absolute_url(article.get('about'))
            if event_link and event_link in seen_links:
                continue
            if event_link:
                seen_links.add(event_link)

            # Dates come from <time datetime="..."> elements in the occurrence list
            times = article.select('.occurrences time.datetime[datetime]')
            start_date = parse_iso_date(times[0]['datetime']) if times else None
            end_date = parse_iso_date(times[-1]['datetime']) if len(times) > 1 else None

            if end_date and end_date < today:
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            else:
                phase = 'current'

            desc_tag = article.select_one('.result-item__excerpt .field__item')
            description = desc_tag.get_text(strip=True) if desc_tag else None

            img_tag = article.select_one('img[src]')
            image_link = absolute_url(img_tag['src']) if img_tag and img_tag.has_attr('src') else None

            event_details = {
                'name': event_title,
                'venue': 'Hammer Museum',
                'description': description,
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
