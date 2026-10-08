from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://wattis.org'
PROGRAM_URL = BASE_URL + '/our-program'

def find_image(event_url):
    """The first real photo on a show's page (the page also has UI icons, as SVG)."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None
    for img in soup.find_all('img', src=True):
        src = img['src']
        if src.lower().endswith('.svg'):
            continue
        return 'https:' + src if src.startswith('//') else BASE_URL + src if src.startswith('/') else src
    return None

def scrape_wattis_institute(env='prod', region='sf'):
    """Scrape and process exhibitions from the CCA Wattis Institute for Contemporary Arts."""

    today = region_today(region)
    # The main program page lists the current and upcoming shows; last year's
    # page (?date=YYYY) holds the recent past ones. Images are only fetched for
    # the former, to avoid a request per past show.
    pages = [(PROGRAM_URL, True), (f'{PROGRAM_URL}?date={today.year - 1}', False)]

    for url, fetch_images in pages:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Wattis Institute: could not fetch {url}; existing data kept.")
            continue

        # Each year lists an "Exhibition Program" and a "Research Program"
        # side by side; only the first is exhibitions.
        container = soup.select_one('div.categoryContainer')
        if not container:
            logging.warning(f"Wattis Institute: no exhibition program found at {url}")
            continue

        for block in container.select('div.block'):
            date_tag = block.find('i')
            link_tag = block.find('a', href=True)
            if not date_tag or not link_tag:
                continue

            name = link_tag.get_text(' ', strip=True)
            start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today)
            if not (start_date or end_date):
                logging.warning(f"Wattis Institute: could not parse dates {date_tag.get_text(strip=True)!r} for {name!r}")
                continue

            phase = derive_phase(start_date, end_date, today) or 'current'
            event_link = BASE_URL + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
            image_link = find_image(event_link) if fetch_images else None

            event_details = {
                'name': name,
                'venue': 'Wattis Institute',
                'description': None,
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
