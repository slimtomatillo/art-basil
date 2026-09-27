from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

def convert_date_to_dt(date_string):
    """Converts a date in string form to a dt.date object."""
    date_parts = date_string.lower().split()
    if len(date_parts) == 3:
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1].replace(',', ''))
        year = int(date_parts[2])
        return dt.date(year, month_num, day)
    else:
        return None


def parse_single_date(text):
    """Best-effort parse of a 'Month [D,] YYYY' fragment found anywhere in text
    (day defaults to the 1st when omitted, e.g. a season name like 'Fall 2027'
    won't match at all - there's no reasonable day to guess). Returns a date or None."""
    match = re.search(
        rf"({'|'.join(MONTH_TO_NUM_DICT.keys())})\.?\s+(?:(\d{{1,2}})\s*,?\s+)?(\d{{4}})",
        text.lower()
    )
    if not match:
        return None
    month, day, year = match.groups()
    return dt.date(int(year), MONTH_TO_NUM_DICT[month], int(day) if day else 1)


def parse_date_label(text):
    """SJMA gives some exhibitions no <time> tag at all - just a plain-text status
    line as the first paragraph, e.g. 'Ongoing Installation', 'Through end of
    October 2025', or 'March 12, 2027 - Fall 2027'. Returns (start, end, ongoing)
    if `text` looks like one of these, else None (treat it as real description)."""
    normalized = ' '.join(text.split())
    if re.match(r'(?i)^ongoing', normalized):
        return None, None, True
    if re.match(r'(?i)^through', normalized):
        end = parse_single_date(normalized)
        return (None, end, False) if end else None
    parts = re.split(r'\s*[–—-]\s*', normalized, maxsplit=1)
    if len(parts) == 2:
        start, end = parse_single_date(parts[0]), parse_single_date(parts[1])
        if start or end:
            return start, end, False
    return None

def scrape_sj_museum_of_art_exhibitions(env='prod', region='sj'):
    """Scrape and process exhibitions from the San Jose Museum of Art."""
    
    def process_exhibitions(url, phase):
        """Process exhibitions from the given URL for the specified phase."""
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping San Jose museum of Art {phase} exhibitions --> no soup found")
            return

        exhibitions = soup.find_all('div', class_='views-row')

        for exhibition in exhibitions:
            # Extract title
            title_tag = exhibition.find('h2')
            event_title = title_tag.text.strip() if title_tag else None

            # Extract link
            event_link_tag = title_tag.find('a') if title_tag else None
            event_link = 'https://sjmusart.org' + event_link_tag['href'] if event_link_tag else None

            # Extract date information
            start_date, end_date, ongoing = None, None, False
            date_tags = exhibition.find_all('time')
            if date_tags:
                # For current exhibitions there is one time tag, which corresponds to the end date
                if phase == 'current':
                    # Check for the datetime attribute first
                    if date_tags[0].has_attr('datetime'):
                        # Parse the datetime attribute if it exists
                        datetime_str = date_tags[0]['datetime']
                        end_date = dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ").date()
                # For future and past exhibitions there are two time tags, one for the start date and one for the end date
                elif phase == 'future' or phase == 'past':
                    # Check for the datetime attribute first
                    if date_tags[0].has_attr('datetime'):
                        # Parse the datetime attribute if it exists
                        datetime_str = date_tags[0]['datetime']
                        start_date = dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ").date()
                    # Check for the datetime attribute first
                    if date_tags[1].has_attr('datetime'):
                        # Parse the datetime attribute if it exists
                        datetime_str = date_tags[1]['datetime']
                        end_date = dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ").date()

            # Some exhibitions (permanent installations, offsite shows) have no <time>
            # tag at all - just a plain-text status line as the first paragraph, e.g.
            # "Ongoing Installation" or "Through end of October 2025". When there's no
            # structured date, try parsing that line; if it looks like a status/date
            # line rather than real description text, use it for dates and skip it
            # below when picking the description.
            abstract_paragraphs = exhibition.select('.field--name-field-abstract p')
            label_result = None
            if not start_date and not end_date:
                first_p_text = abstract_paragraphs[0].get_text(strip=True) if abstract_paragraphs else None
                if first_p_text:
                    label_result = parse_date_label(first_p_text)
                    if label_result:
                        start_date, end_date, ongoing = label_result

            # Extract description - the first paragraph that isn't a date/status label
            description_paragraphs = abstract_paragraphs[1:] if label_result else abstract_paragraphs
            description_text = description_paragraphs[0].get_text(separator=' ').strip() if description_paragraphs else None

            # Extract image if available
            img_tag = exhibition.find('img')
            image_link = 'https://sjmusart.org' + img_tag['src'] if img_tag else None
                        
            event_details = {
                'name': event_title,
                'venue': 'San Jose Museum of Art',
                'description': description_text,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}] if event_link else [],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            # Add logging for dev environment
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)

    # On View Exhibitions
    process_exhibitions('https://sjmusart.org/exhibitions-on-view', 'current')

    # Upcoming Exhibitions
    process_exhibitions('https://sjmusart.org/upcoming-exhibitions', 'future')

    # Past Exhibitions
    process_exhibitions('https://sjmusart.org/past-exhibitions', 'past')
