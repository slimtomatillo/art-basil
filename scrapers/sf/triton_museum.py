from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://www.tritonmuseum.org'

# Wix site. Current and Upcoming are separate pages, each a repeater of
# "EXHIBITION / title / artist / DATES" text blocks with an (unlabelled) link
# per block. Dates carry no year ("AUG 29 - JAN 10"), so the year is inferred
# from today - fine for current/upcoming shows, but not for the Past page,
# which is why that page (which does show years, but runs 2+ years behind) is
# skipped; shows age into 'past' on their own once their end date passes.
PAGES = [
    (BASE_URL + '/on-view', '/on-view/', 'current'),
    (BASE_URL + '/upcoming-exhibitions', '/upcoming-exhibitions/', 'future'),
]

_ZERO_WIDTH = dict.fromkeys(map(ord, '​‌‍﻿'))
_DATE_LINE_RE = re.compile(r'^[A-Za-z]{3,5}\.?\s+\d{1,2}\s*[-–]\s*[A-Za-z]{3,5}\.?\s+\d{1,2}$')

def parse_blocks(soup):
    """Split the page text into (title, artist, date_text) per 'EXHIBITION' label."""
    lines = [l.translate(_ZERO_WIDTH).strip() for l in soup.get_text('\n', strip=True).split('\n')]
    lines = [l for l in lines if l]
    blocks, current = [], None
    for line in lines:
        if line == 'EXHIBITION':
            current = []
            blocks.append(current)
        elif current is not None:
            current.append(line)
            if _DATE_LINE_RE.match(line):
                current = None
    result = []
    for block in blocks:
        if block and _DATE_LINE_RE.match(block[-1]):
            title, *middle = block[:-1]
            result.append((title, middle[0] if middle else None, block[-1]))
    return result

def find_event_page(event_url):
    """Returns (description, image) from a show's page."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None, None
    og_image = soup.find('meta', property='og:image')
    og_description = soup.find('meta', property='og:description')
    return (og_description.get('content') if og_description else None,
            og_image.get('content') if og_image else None)

def scrape_triton_museum(env='prod', region='sf'):
    """Scrape and process current and upcoming exhibitions from the Triton Museum of Art."""

    today = region_today(region)

    for url, link_prefix, tab_phase in PAGES:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Triton Museum: could not fetch {url}; existing data kept.")
            continue

        blocks = parse_blocks(soup)
        links = []
        for a in soup.find_all('a', href=True):
            if link_prefix in a['href'] and a['href'] not in links:
                links.append(a['href'])
        if len(links) != len(blocks):
            logging.warning(f"Triton Museum: found {len(blocks)} exhibitions but {len(links)} links at {url}; "
                            f"falling back to the listing page for links")

        for i, (title, artist, date_text) in enumerate(blocks):
            start_date, end_date = parse_date_text(date_text, today)
            if not (start_date or end_date):
                logging.warning(f"Triton Museum: could not parse dates {date_text!r} for {title!r}")
                continue

            # Some titles already include the artist ("Rose Sellery: Fragile Strength")
            name = f"{title} by {artist}" if artist and artist.lower() not in title.lower() else title
            phase = derive_phase(start_date, end_date, today) or tab_phase
            event_link = links[i] if len(links) == len(blocks) else url
            description, image_link = (find_event_page(event_link) if event_link != url else (None, None))

            event_details = {
                'name': name,
                'venue': 'Triton Museum of Art',
                'description': description,
                'tags': ['exhibition'] + [phase] + ['museum'],
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
