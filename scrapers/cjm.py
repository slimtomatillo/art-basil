from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_string):
    """Takes a date in string form and converts it to a dt object"""

    date_parts = date_string.split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    day = int(date_parts[1])
    year = int(date_parts[2])
    if month_num and day and year:
        date_dt = dt.date(year, month_num, day)
    return date_dt

def scrape_contemporary_jewish_museum(env='prod'):
    """Scrape and process events from Contemporary Jewish Museum."""
    
    # Declare list of urls
    urls = [
        {
            'url': 'https://www.thecjm.org/current_exhibitions',
            'phase': 'current'
        },
        {
            'url': 'https://www.thecjm.org/upcoming_exhibitions',
            'phase': 'future'
        },
        {
            'url': 'https://www.thecjm.org/past_exhibitions',
            'phase': 'past'
        }
    ]
    
    # Go through and collect events in each phase (current, future, and past)
    for url_dict in urls:
    
        # Scrape info
        soup = fetch_and_parse(url_dict['url'])
                
        # Find all events
        events_list = soup.find_all(class_='exhibitions__section')

        # Check if events is found
        if events_list:
            
            for event in events_list:
                # Extract title and title-link
                title_tag = event.find('h3', class_='exhibition__title').find('a', class_='title-link')
                if title_tag:
                    event_title = title_tag.text.strip()
                    event_link = 'https://thecjm.org' + title_tag['href']
                else:
                    event_title, event_link = None, None

                # Extract image link if possible
                try:
                    image_link = event.find('a')['style'].split('(')[1].split(')')[0]
                except IndexError:
                    image_link = None

                # Extract date-label
                event_dates = event.find('p', class_='exhibition__date-label').find_all('span')
                event_dates = '–'.join([span.text.strip() for span in event_dates]) if event_dates else None
                dates = event_dates.lower().replace(',', '').split('––')
                if event_dates.lower() == 'ongoing exhibit':
                    start_date = None
                    end_date = None
                    ongoing = True
                else:
                    start_date = convert_date_to_dt(dates[0])
                    end_date = convert_date_to_dt(dates[1])
                    ongoing = False
                
                # Extract rich-text (description)
                description_tag = event.find('div', class_='rich-text')
                event_description = description_tag.get_text(separator='\n').strip() if description_tag else None
                if event_description:
                    clean_description = event_description.replace('\n', ' ').replace('\xa0', ' ')
                    normalized_description = ' '.join(clean_description.split())
                    event_description = normalized_description

                event_details = {
                    'name': event_title,
                    'venue': 'Contemporary Jewish Museum',
                    'description': event_description,
                    'tags': ['exhibition'] + [url_dict['phase']] + ['museum'],
                    'phase': url_dict['phase'],
                    'dates': {'start': start_date, 'end': end_date},
                    'ongoing': ongoing,
                    'links': [
                        {
                            'link': event_link,
                            'description': 'Event Page'
                        },
                    ],
                    'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                }
                # Add image link if it exists
                if image_link:
                    event_details['links'].append({
                        'link': image_link,
                        'description': 'Image'
                    })

                if env == 'prod':
                    process_event(event_details)

        else:
            logging.warning(f"Events not found for phase: {url_dict['phase']}")