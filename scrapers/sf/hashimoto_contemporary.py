from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from scrapers.sf._artlogic import artlogic_items, parse_day_first_range
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://www.hashimotocontemporary.com'
# One site covers the New York and San Francisco galleries; each listing names its location
PAGES = (BASE_URL + '/exhibitions/current/', BASE_URL + '/exhibitions/forthcoming/')


def single_exhibition(soup):
    """The one show a "current" or "upcoming" page now holds, as artlogic_items would give it, or None. These pages used to be lists;
    since the site changed (WEBSITE-123) each is a single exhibition's page, titled "Name | 5 December 2026 - 2 January 2027" with the
    gallery ("Hashimoto Contemporary SF" or "NYC") in span.location, and the show's own address in the canonical link."""
    heading = soup.select_one('h1 .h1_heading') or soup.find('h1')
    og = soup.find('meta', property='og:title')
    canonical = soup.find('link', rel='canonical')
    if not (heading and og and og.get('content') and canonical and canonical.get('href')):
        return None
    name = heading.get_text(' ', strip=True)
    _, _, date_text = og['content'].partition(' | ')
    location = soup.select_one('span.location')
    if not (name and date_text.strip()):
        return None
    return {'name': name, 'date_text': date_text.strip(), 'location': location.get_text(' ', strip=True) if location else '',
            'description': None, 'link': canonical['href']}


def scrape_hashimoto_contemporary(env='prod', region='sf'):
    """Scrape and process the San Francisco shows of Hashimoto Contemporary."""

    today = region_today(region)
    found = 0
    seen = set()
    for url in PAGES:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Hashimoto Contemporary: could not fetch {url}; existing data kept.")
            continue
        items = list(artlogic_items(soup, BASE_URL))
        if not items and single_exhibition(soup):
            items = [single_exhibition(soup)]
        for item in items:
            if item['location'].strip().upper().endswith('NYC') or 'SF' not in item['location'].upper().split():
                continue
            if item['link'] in seen:
                continue
            seen.add(item['link'])
            start_date, end_date = parse_day_first_range(item['date_text'])
            if not (start_date and end_date):
                logging.warning(f"Hashimoto Contemporary: no readable dates for {item['name']!r}")
                continue
            phase = derive_phase(start_date, end_date, today) or 'current'
            if phase == 'past':
                continue
            event_details = {
                'name': item['name'],
                'venue': 'Hashimoto Contemporary',
                'description': item['description'],
                'tags': ['exhibition'] + [phase] + ['gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': item['link'], 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            found += 1
            if env == 'dev':
                logging.info(f"Event found: {item['name']} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
            if env == 'prod':
                process_event(event_details, region)

    if not found:
        logging.warning("Hashimoto Contemporary: no San Francisco shows found; existing data kept.")
