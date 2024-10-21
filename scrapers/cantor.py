from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_string):
    """Takes a date in string form and converts it to a dt object"""
    
    # Handle 'ongoing'
    if date_string == 'ongoing':
        return None

    date_parts = date_string.split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    day = int(date_parts[1])
    year = int(date_parts[2])
    if month_num and day and year:
        date_dt = dt.date(year, month_num, day)
    return date_dt

def scrape_cantor_exhibitions(env='prod'):
    """Scrape and process exhibitions from the Cantor Arts Center at Stanford University."""
    
    # Create dict to map our phases to the ones used by the venue
    phase_dict = {
        'current': 'current',
        'future': 'upcoming',
        'past': 'past',
    }

    def process_exhibitions(url, phase):
        """Process exhibitions for a given URL and phase (current, future, past)."""
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping Cantor Arts Center {phase} exhibitions --> no soup found")
            return
        
        # Define class based on phase
        phase_class = f'view--exhibitions--block-exhibitions-{phase_dict[phase]}'
        
        try:
            exhibition_section = soup.find_all('div', class_=phase_class)[0]

        except Exception as e:
            logging.warning(f"Error scraping Cantor Arts Center {phase} exhibitions: {e}")
            
        events = exhibition_section.find_all('div', class_='container')
                        
        for event_element in events:
            title = event_element.find('a').text.strip()
            
            # Dates
            date_range = event_element.find('div', class_='exhibition__dynamic-token-fieldnode-start-date-to-end-date').text.strip()
            # Mark 'ongoing' flag
            ongoing = True if 'ongoing' in date_range.lower() else False
            dates = date_range.lower().replace(',', '').split('–')
            # Get dt versions of start and end dates
            if len(dates[0].split()) == 2:
                dates[0] = dates[0] + ' ' + dates[1].split()[-1]
            start_date = convert_date_to_dt(dates[0])
            end_date = convert_date_to_dt(dates[1])

            event_link_tag = event_element.find('a')
            event_link = 'https://museum.stanford.edu' + event_link_tag['href'] if event_link_tag else None
            
            image_tag = event_element.find('img', src=True)
            image_link = 'https://museum.stanford.edu' + image_tag['src'] if image_tag else None
            
            event_details = {
                'name': title,
                'venue': 'Cantor Arts Center',
                'description': '',
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'prod':
                process_event(event_details)

    # Scrape current exhibitions
    current_url = 'https://museum.stanford.edu/exhibitions'
    process_exhibitions(current_url, 'current')

    # Scrape future exhibitions
    upcoming_url = 'https://museum.stanford.edu/exhibitions/upcoming-exhibitions'
    process_exhibitions(upcoming_url, 'future')

    # Scrape past exhibitions
    past_url = 'https://museum.stanford.edu/exhibitions/past-exhibitions'
    process_exhibitions(past_url, 'past')