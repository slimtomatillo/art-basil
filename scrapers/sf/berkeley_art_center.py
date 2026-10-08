from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://www.berkeleyartcenter.org'
ON_VIEW_URL = BASE_URL + '/on-view'

# Only the On View / Upcoming page is scraped. Past shows live on hand-laid-out
# per-year pages (/2026, /2025, ...) with no consistent structure (all-caps
# titles, long artist lists, mixed date styles), so they aren't parsed - shows
# scraped here age into 'past' on their own once their end date passes.
SECTION_PHASES = {'on view': 'current', 'upcoming': 'future'}

def slugify(title):
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

def split_sections(main):
    """Squarespace puts each section under an <h1> ('on view', 'upcoming');
    group the elements that follow it, in document order, until the next <h1>."""
    sections = []
    for el in main.find_all(['h1', 'h2', 'h3', 'p', 'a', 'img']):
        if el.name == 'h1':
            sections.append({'name': el.get_text(' ', strip=True).lower(), 'els': []})
        elif sections:
            sections[-1]['els'].append(el)
    return sections

def scrape_berkeley_art_center(env='prod', region='sf'):
    """Scrape and process current and upcoming exhibitions from the Berkeley Art Center."""

    today = region_today(region)
    soup = fetch_and_parse(ON_VIEW_URL)
    if soup is None:
        logging.warning("Berkeley Art Center: could not fetch the on-view page; existing data kept.")
        return
    main = soup.find('main') or soup
    for tag in main(['script', 'style']):
        tag.decompose()

    internal_links = [a['href'] for a in main.find_all('a', href=True) if a['href'].startswith('/')]

    for section in split_sections(main):
        tab_phase = SECTION_PHASES.get(section['name'])
        if not tab_phase:
            continue
        els = section['els']

        title_tag = next((e for e in els if e.name == 'h2'), None)
        name = title_tag.get_text(' ', strip=True) if title_tag else ''
        if not name or name.lower() == 'coming soon':
            continue

        start_date = end_date = None
        for h3 in (e for e in els if e.name == 'h3'):
            start_date, end_date = parse_date_text(h3.get_text(' ', strip=True), today)
            if start_date or end_date:
                break
        if not (start_date or end_date):
            logging.warning(f"Berkeley Art Center: no readable dates for {name!r}")
            continue

        phase = derive_phase(start_date, end_date, today) or tab_phase

        # The title isn't itself linked on this page; the show's own page is
        # the internal link whose slug matches its title, else the first one.
        slug = slugify(name)
        own_links = [l for l in internal_links if l.strip('/') == slug]
        event_link = BASE_URL + (own_links or [l for l in (e.get('href') for e in els if e.name == 'a') if l and l.startswith('/')] or ['/on-view'])[0]

        image_tag = next((e for e in els if e.name == 'img'), None)
        image_link = (image_tag.get('data-src') or image_tag.get('src')) if image_tag else None

        description = next((e.get_text(' ', strip=True) for e in els
                            if e.name == 'p' and len(e.get_text(strip=True)) > 60), None)

        event_details = {
            'name': name,
            'venue': 'Berkeley Art Center',
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
