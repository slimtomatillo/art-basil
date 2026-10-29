from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

HOME_URL = 'https://www.marinsocietyofartists.org'

# The gallery's monthly shows have no listing page (the Exhibitions page is just
# a blurb). Each juried/annual show gets its own page, linked in the site menu
# under FOR ARTISTS; those pages carry an "Exhibition dates:" line.
_MENU_START = 'for artists'
_MENU_END = 'calls for entry'
_DATES_RE = re.compile(r'exhibition dates\s*:?\s*([^\n]+)', re.I)
_MAX_DESCRIPTION = 400


def _show_pages(soup):
    """(title, url) of the show pages in the FOR ARTISTS menu section."""
    pages, inside = [], False
    for a in soup.find_all('a', href=True):
        label = a.get_text(' ', strip=True)
        if label.lower() == _MENU_START:
            inside = True
        elif label.lower() == _MENU_END:
            break
        elif inside and label:
            pages.append((label, a['href']))
    return pages


def scrape_marin_society_of_artists(env='prod', region='sf'):
    """Scrape and process the show pages of the Marin Society of Artists."""

    today = region_today(region)
    home = fetch_and_parse(HOME_URL)
    if home is None:
        logging.warning("Marin Society of Artists: could not fetch the home page; existing data kept.")
        return

    pages = _show_pages(home)
    if not pages:
        logging.warning("Marin Society of Artists: no show pages found in the menu; existing data kept.")
        return

    for title, url in pages:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        text = soup.get_text('\n', strip=True)
        if 'cancel' in text.lower():
            continue
        m = _DATES_RE.search(text)
        if not m:
            continue
        # Dates can sit on the line after the label
        date_text = m.group(1)
        if not re.search(r'\d', date_text):
            after = text[m.end():].split('\n')
            date_text = next((l for l in after if re.search(r'\d', l)), '')
        # Stop before trailing text such as "Reception Friday, October 9"
        date_text = re.split(r'\s+reception\b', date_text, flags=re.I)[0]
        start_date, end_date = parse_date_text(date_text, today)
        if not (start_date and end_date):
            logging.warning(f"Marin Society of Artists: no readable dates for {title!r}")
            continue

        name = title if title.lower().startswith('msa') else f'MSA {title}'
        online = 'online' in text.lower().split('exhibition dates')[0][-60:]
        phase = derive_phase(start_date, end_date, today) or 'current'
        meta = soup.find('meta', property='og:description')
        description = ' '.join(meta['content'].split())[:_MAX_DESCRIPTION] if meta and meta.get('content') else None

        event_details = {
            'name': name,
            'venue': 'Marin Society of Artists',
            'description': description,
            'tags': ['exhibition'] + [phase] + ['gallery'] + (['online'] if online else []),
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': url, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
