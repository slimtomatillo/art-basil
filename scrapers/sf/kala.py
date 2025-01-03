from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

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

def scrape_kala_exhibitions(env='prod', region='sf'):
    """Scrape and process exhibitions from the Kala Art Institute."""
    
    url = 'https://www.kala.org/gallery/exhibitions/'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.ingo('Error scraping Kala exhibitions')
        return

    # Find current exhibitions
    current_exhibition_section = soup.find('section', id='kala-gallery', class_='section-current-exhibition')
    if current_exhibition_section:
        try:
            title = current_exhibition_section.find('h3').text.strip()
            date_range = current_exhibition_section.find('div', class_='exhibition-copy').find_next('p').text.strip()
            dates = date_range.lower().replace('             ', '').replace(',', '').split(' — ')
            start_date = convert_date_to_dt(dates[0])
            end_date = convert_date_to_dt(dates[1]) if len(dates) > 1 else None

            description = current_exhibition_section.find('div', class_='exhibition-copy').find_next('p').find_next('p').text.strip()
            description = description.replace('\n', ' ').replace('\xa0', ' ')
            
            phase = 'current'
            
            event_link_tag = current_exhibition_section.find('a', text='View Exhibition')
            event_link = event_link_tag['href'] if event_link_tag else None

            image_tag = current_exhibition_section.find('img', src=True)
            image_link = image_tag['src'] if image_tag else None

            event_details = {
                'name': title,
                'venue': 'Kala Art Institute',
                'description': description,
                'tags': ['exhibition', phase, 'gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False, # Kala does not have any ongoing exhibitions
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            # Process event in dev environment
            if env == 'dev':
                logging.info(f"Event details - Name: {event_details['name']}, Venue: {event_details['venue']}")

            if env == 'prod':
                process_event(event_details, region)

        except AttributeError as e:
            logging.info(f"Error parsing element: {e}")