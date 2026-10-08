from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://anderson.stanford.edu'
LISTING_URL = BASE_URL + '/programs-exhibitions/'

# Uses the Anderson's own site, not museum.stanford.edu (which is behind
# Cloudflare). The listing page has no dates, so each show's own page is read
# for its "<date> - <date or Ongoing>" line.
_RANGE_RE = re.compile(r'([A-Z][a-z]+\.? \d{1,2}, \d{4})\s*[-–]\s*(Ongoing|[A-Z][a-z]+\.? \d{1,2}, \d{4})')

def scrape_event_page(event_url, today):
    """Returns (name, start, end, ongoing, description) from a show's page."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None
    title = soup.title.get_text(strip=True).split('|')[0].strip() if soup.title else None

    text = soup.get_text('\n', strip=True)
    m = _RANGE_RE.search(text)
    if not m:
        return None
    ongoing = m.group(2) == 'Ongoing'
    if ongoing:
        start_date, _ = parse_date_text(m.group(1), today)
        end_date = None
    else:
        start_date, end_date = parse_date_text(f"{m.group(1)} - {m.group(2)}", today)

    meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    description = ' '.join(meta['content'].split()) if meta and meta.get('content') else None
    return title, start_date, end_date, ongoing, description

def scrape_anderson_collection(env='prod', region='sf'):
    """Scrape and process exhibitions from the Anderson Collection at Stanford University."""

    today = region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Anderson Collection: could not fetch the exhibitions page; existing data kept.")
        return

    # Show pages live at /exhibitions/<slug>/ (the bare /exhibitions/ is an
    # index). Each show's image is only on the listing page, inside one of the
    # links to it, so gather the first image per show before visiting each.
    show_images = {}
    for a in soup.select('#main a[href]'):
        href = a['href'].split('#')[0]
        if not re.match(rf'^{re.escape(BASE_URL)}/exhibitions/[^/]+/?$', href):
            continue
        img = a.find('img', src=True)
        show_images.setdefault(href, img['src'] if img else None)
        if img and not show_images[href]:
            show_images[href] = img['src']

    for href, image_link in show_images.items():
        details = scrape_event_page(href, today)
        if not details:
            logging.warning(f"Anderson Collection: no readable dates at {href}")
            continue
        name, start_date, end_date, ongoing, description = details
        if not name:
            continue

        phase = derive_phase(start_date, end_date, today) or 'current'

        event_details = {
            'name': name,
            'venue': 'Anderson Collection',
            'description': description,
            'tags': ['exhibition'] + [phase] + ['museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing and phase == 'current',
            'links': [{'link': href, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
