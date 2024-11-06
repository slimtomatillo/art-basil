from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

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

def scrape_sj_museum_of_art_exhibitions(env='prod'):
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
                        
            # Extract description
            description_tag = exhibition.find('p')
            description_text = description_tag.get_text(separator=' ').strip() if description_tag else None

            # Extract image if available
            img_tag = exhibition.find('img')
            image_link = 'https://sjmusart.org' + img_tag['src'] if img_tag else None

            # Handle edge cases
            if phase == 'current' and event_title == 'Hidden Heritages: San José’s Vietnamese Legacy':
                ongoing = True
            elif phase == 'current' and event_title == 'Koret Gallery: Art Learning Lab':
                ongoing = True
            elif phase == 'current' and event_title == 'Pae White: Noisy Blushes':
                ongoing = True
                        
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

            if env == 'prod':
                process_event(event_details)

    # On View Exhibitions
    process_exhibitions('https://sjmusart.org/exhibitions-on-view', 'current')

    # Upcoming Exhibitions
    process_exhibitions('https://sjmusart.org/upcoming-exhibitions', 'future')

    # Past Exhibitions
    process_exhibitions('https://sjmusart.org/past-exhibitions', 'past')
