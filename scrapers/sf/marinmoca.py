from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
from urllib.parse import urljoin

BASE_URL = 'https://www.marinmoca.org'
EXHIBITIONS_URL = BASE_URL + '/see-and-experience'


def _build_event(name, start_date, end_date, link, image, today):
    phase = derive_phase(start_date, end_date, today) or 'current'
    event_details = {
        'name': name,
        'venue': 'Marin Museum of Contemporary Art',
        'description': None,
        'tags': ['exhibition'] + [phase] + ['museum'],
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': False,
        'links': [{'link': link, 'description': 'Event Page'}],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if image:
        event_details['links'].append({'link': image, 'description': 'Image'})
    return event_details


def scrape_marinmoca(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions of MarinMOCA."""

    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("MarinMOCA: could not fetch the exhibitions page; existing data kept.")
        return

    found = []

    # The show on view is the page's lead block: a heading followed by a bolded
    # date range. It is not part of the "Exhibitions" list below it.
    for strong in soup.find_all('strong'):
        if strong.find_parent(class_='summary-item'):
            continue
        start_date, end_date = parse_date_text(strong.get_text(' ', strip=True), today)
        if not (start_date and end_date):
            continue
        heading = strong.find_previous(['h1', 'h2', 'h3'])
        if heading is None:
            continue
        image = soup.find('meta', property='og:image')
        found.append((heading.get_text(' ', strip=True), start_date, end_date,
                      EXHIBITIONS_URL, image['content'] if image and image.get('content') else None))
        break

    # The list holds Upcoming and Past shows; only upcoming ones are kept (Past is
    # an archive back to 2024, and a show ages into 'past' by its own end date).
    for item in soup.select('div.summary-item'):
        tags = [t.get_text(strip=True) for t in item.select('.summary-metadata-item--tags')]
        if 'Upcoming Exhibitions' not in tags:
            continue
        title_tag = item.select_one('.summary-title')
        date_tag = item.select_one('.summary-excerpt')
        link_tag = item.select_one('a[href]')
        if not (title_tag and date_tag and link_tag):
            continue
        start_date, end_date = parse_date_text(date_tag.get_text(' ', strip=True), today)
        if not (start_date or end_date):
            logging.warning(f"MarinMOCA: no readable dates for {title_tag.get_text(strip=True)!r}")
            continue
        img = item.find('img')
        image = (img.get('data-src') or img.get('src')) if img else None
        found.append((title_tag.get_text(' ', strip=True), start_date, end_date,
                      urljoin(BASE_URL, link_tag['href']), image))

    if not found:
        logging.warning("MarinMOCA: no exhibitions found; existing data kept.")

    for name, start_date, end_date, link, image in found:
        event_details = _build_event(name, start_date, end_date, link, image, today)
        if env == 'dev':
            logging.info(f"Event found: {name} ({event_details['phase']}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
