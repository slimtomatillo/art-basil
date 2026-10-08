from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

_MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
_WEEKDAY_RE = r'(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)\w*,\s*'
# OMCA's date-range header is inconsistent: an optional weekday name on either
# side, either dash character as the separator, the start year often omitted
# (inferred from the end year), an optional trailing " | <Location>", and
# occasionally a 4-digit year split by a stray space from an inline element
# boundary ("202 6").
_DATE_RANGE_RE = re.compile(
    rf'(?:{_WEEKDAY_RE})?({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{3}}\s?\d)?'
    rf'\s*[\u2013\u2014-]\s*'
    rf'(?:{_WEEKDAY_RE})?({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{3}}\s?\d)',
    re.IGNORECASE
)


def parse_date_range(text):
    """Extract (start_date, end_date) from an OMCA date-range header, or
    (None, None) if it doesn't look like one."""
    match = _DATE_RANGE_RE.search(text)
    if not match:
        return None, None
    m1, d1, y1, m2, d2, y2 = match.groups()
    y2 = y2.replace(' ', '')
    y1 = (y1 or y2).replace(' ', '')
    try:
        start_date = dt.date(int(y1), MONTH_TO_NUM_DICT[m1.lower()], int(d1))
        end_date = dt.date(int(y2), MONTH_TO_NUM_DICT[m2.lower()], int(d2))
    except (ValueError, KeyError):
        return None, None
    return start_date, end_date


def convert_date_to_dt(date_text):
    """Convert date text to a datetime object, determining the year based on the next occurrence."""

    # Get current date
    today = dt.date.today()
    current_year = today.year

    # Split the date text
    date_parts = date_text.lower().strip().split()
    month_str = date_parts[0]
    day = int(date_parts[1])

    # Convert month to number
    month = MONTH_TO_NUM_DICT[month_str]

    # Determine if the year is provided
    if len(date_parts) == 3:
        year = int(date_parts[2])
    else:
        # Determine the year based on the next occurrence of the date
        if month < today.month or (month == today.month and day < today.day):
            year = current_year + 1
        else:
            year = current_year

    # Create the date object
    return dt.date(year, month, day)

def scrape_oak_museum_of_ca_exhibitions(env='prod', region='sf'):
    """Scrape and process events from the Oakland Museum of California (OMCA)."""
    
    def fetch_event_details(event_url):
        """Fetch and parse details from the event's page."""
        
        event_soup = fetch_and_parse(event_url)
        if not event_soup:
            return None, None, None

        # Find all header tags (h1, h2, h3, h4, h5, h6)
        header_tags = event_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for header in header_tags:
            date_text = header.get_text(strip=True).lower().replace('-', '–').replace('—', '–') # make dashes the same
            # Handle edge cases
            if '“' in date_text:
                continue

            if any(keyword in date_text for keyword in ['now on view', 'on view now', 'opens', 'on view through', 'ongoing', '–']):
                # Check for certain header tags to skip
                if date_text.strip() == 'angela davis–seize the time':
                    continue
                # Exhibition is on view
                elif 'now on view' in date_text:
                    return None, None, True
                # On view now
                elif 'on view now' in date_text:
                    # Handle 'Calli: The Art of Xicanx Peoples'
                    if event_url == 'https://museumca.org/on-view/calli-the-art-of-xicanx-peoples/':
                        return convert_date_to_dt('june 14 2024'), convert_date_to_dt('january 26 2025'), False
                    else:
                        return None, None, True
                # Ongoing exhibition
                elif 'on view through' in date_text:
                    return None, None, True
                # Ongoing exhibition
                elif 'ongoing' in date_text:
                    return None, None, True
                # Opening in the future
                elif 'opens' in date_text:
                    date_text = date_text.replace('opens ', '').split(' | ')
                    start_date = convert_date_to_dt(date_text[0])
                    return start_date, None, False
                # Date range, e.g. "On view Friday, February 7, 2025–Sunday,
                # February 1, 2026 | Gallery of California Art" - search() finds
                # the range regardless of a leading "on view"/trailing location
                elif '–' in date_text:
                    start_date, end_date = parse_date_range(date_text)
                    if start_date is None and end_date is None:
                        logging.warning(f"OMCA: could not parse date range {date_text!r} for {event_url}")
                        continue
                    return start_date, end_date, False

        # Otherwise, it's a past exhibition
        title_tag = event_soup.find('h1', class_='wp-block-post-title')
        date_text = title_tag.find_next('p') if title_tag else None
        if date_text:
            start_date, end_date = parse_date_range(date_text.get_text(strip=True).lower())
            if start_date or end_date:
                return start_date, end_date, False

        return None, None, False

    url = 'https://museumca.org/on-view/#exhibitions'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.info('Error scraping OMCA exhibitions')
        return

    exhibition_elements = soup.find_all('div', class_='post-tile post-tile_type-on-view')

    for elem in exhibition_elements:
        # Reset so a tile that fails before its link is read doesn't log the
        # previous tile's link in the warning below.
        event_link = None
        try:
            # Tiles with no excerpt are OMCA's permanent galleries (Gallery of
            # California Art/History/Natural Sciences, the Garden): they are
            # part of the museum rather than shows, so they are not listed.
            excerpt_tag = elem.find('span', class_='post-tile__excerpt')
            if excerpt_tag is None:
                continue

            # Extract title. Joined with spaces in case a title is split
            # across a <br>.
            title = ' '.join(elem.find('span', class_='post-tile__title').get_text(' ', strip=True).split())

            # Extract description
            description = excerpt_tag.text.strip().replace('\n', '').replace('\xa0', ' ')

            # Extract location
            location_tag = elem.find('span', class_='post-tile__tax-location')
            location = location_tag.text.strip() if location_tag else None

            # Extract event link
            event_link_tag = elem.find('a', class_='post-tile__inner', href=True)
            event_link = event_link_tag['href'] if event_link_tag else None
            
            # Extract dates
            start_date, end_date, ongoing = fetch_event_details(event_link)

            # Extract image link
            image_tag = elem.find('img', src=True)
            image_link = image_tag['src'] if image_tag else None

            # Identify phase
            today = dt.datetime.today().date()
            if start_date != None and end_date != None:
                if start_date <= today <= end_date:
                    phase = 'current'
                elif today < start_date:
                    phase = 'future'
                else:
                    phase = 'past'
            elif ongoing == True:
                phase = 'current'
            else:
                phase = None

            event_details = {
                'name': title,
                'venue': 'Oakland Museum of California',
                'description': description,
                'tags': ['exhibition', phase, 'museum'] if phase else ['exhibition', 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Add image link if it exists
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            # Add logging for dev environment
            if env == 'dev':
                logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")

            if env == 'prod':
                process_event(event_details, region)

        except Exception as e:
            tile_title = elem.find('span', class_='post-tile__title')
            logging.warning(f"Error parsing OMCA tile {tile_title.get_text(strip=True) if tile_title else '?'!r}: {e}")
            continue