from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://minnesotastreetproject.com'
EXHIBITIONS_URL = BASE_URL + '/exhibitions'

# The past listing is a long paginated archive; only the most recent pages
# are worth re-scraping daily. Every page also repeats the Current and
# Upcoming sections, so shows are de-duplicated by link.
MAX_PAGES = 3

def scrape_minnesota_street_project(env='prod', region='sf'):
    """Scrape and process exhibitions from the galleries at Minnesota Street Project."""

    today = region_today(region)
    seen_links = set()

    for page in range(MAX_PAGES):
        url = EXHIBITIONS_URL if page == 0 else f'{EXHIBITIONS_URL}?page={page}'
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Minnesota Street Project: could not fetch {url}; existing data kept.")
            continue

        for item in soup.select('div.item'):
            title_tag = item.find('h3')
            link_tag = title_tag.find('a', href=True) if title_tag else None
            date_tag = item.find('p')
            if not link_tag or not date_tag:
                continue

            event_link = BASE_URL + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
            if event_link in seen_links:
                continue
            seen_links.add(event_link)

            name = ' '.join((link_tag.get('title') or link_tag.get_text(' ', strip=True)).split())

            # First line of the paragraph is the date range, second is
            # "<address> / <gallery name>" for the gallery hosting the show.
            lines = [line for line in date_tag.get_text('\n', strip=True).split('\n') if line]
            start_date, end_date = parse_date_text(lines[0], today)
            if not (start_date or end_date):
                logging.warning(f"Minnesota Street Project: could not parse dates {lines[0]!r} for {name!r}")
                continue
            gallery = lines[1] if len(lines) > 1 else None

            phase = derive_phase(start_date, end_date, today) or 'current'

            image_tag = item.find('img', src=True)
            image_link = None
            if image_tag:
                src = image_tag['src']
                image_link = BASE_URL + src if src.startswith('/') else src

            event_details = {
                'name': name,
                'venue': 'Minnesota Street Project',
                'description': f"At {gallery}" if gallery else None,
                'tags': ['exhibition'] + [phase] + ['gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'dev':
                logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
            if env == 'prod':
                process_event(event_details, region)
