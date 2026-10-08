from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

CURRENT_URL = 'https://richmondartcenter.org/exhibition/'

# Only the "Current Exhibitions" listing is scraped. The cards carry no dates,
# so each show's own page is read for its "Exhibition: <dates>" line; shows
# age into 'past' on their own once their end date passes.
_EXHIBITION_LINE_RE = re.compile(r'Exhibition\s*:\s*([^\n]+)')

def scrape_event_page(event_url, today):
    """Returns (start, end, description) read from a show's own page."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None, None, None
    text = soup.get_text('\n', strip=True)
    # The label and its value can be split across lines ("Exhibition" / ": Sept 2 - Nov 19")
    flat = re.sub(r'\s*\n\s*', ' ', text)
    m = _EXHIBITION_LINE_RE.search(flat)
    start_date, end_date = (None, None)
    if m:
        # Stop at the next label so trailing text ("Opening Reception: ...") isn't parsed too
        date_text = re.split(r'\s+(?:Opening|Reception|Location|Gallery)\b', m.group(1))[0]
        start_date, end_date = parse_date_text(date_text, today)
    meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    description = ' '.join(meta['content'].split()) if meta and meta.get('content') else None
    return start_date, end_date, description

def scrape_richmond_art_center(env='prod', region='sf'):
    """Scrape and process current exhibitions from the Richmond Art Center."""

    today = region_today(region)
    soup = fetch_and_parse(CURRENT_URL)
    if soup is None:
        logging.warning("Richmond Art Center: could not fetch the exhibitions page; existing data kept.")
        return

    for card in soup.select('div.esg-grid li'):
        link_tag = card.find('a', href=True)
        title_tag = card.select_one('.esg-center')
        if not link_tag or not title_tag:
            continue
        name = title_tag.get_text(' ', strip=True)
        event_link = link_tag['href']

        start_date, end_date, description = scrape_event_page(event_link, today)
        if not (start_date or end_date):
            logging.warning(f"Richmond Art Center: no readable dates for {name!r}")
            continue

        phase = derive_phase(start_date, end_date, today) or 'current'

        image_tag = card.find('img', src=True)
        image_link = image_tag['src'] if image_tag else None

        event_details = {
            'name': name,
            'venue': 'Richmond Art Center',
            'description': description,
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
