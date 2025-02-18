from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def scrape_event_specific_page(event_url):
    """Given the url for a specific event, scrape info"""

    # Scrape info and collect events
    soup = fetch_and_parse(event_url)

    # Find all <p> elements within <header class="article-header">
    header = soup.find('header', class_='article-header')
    if not header:
        return None, None, None
        
    p_elements = header.find_all('p')

    # Get date info
    event_dates = None
    for p in p_elements:
        text = p.text.strip().lower()
        # Skip if this looks like a title, opening reception, or other non-date text
        if any(skip in text for skip in ['sfwa', 'members', 'exhibition', 'opening reception', 'opening', 'reception']):
            continue
        # Look for date separator and ensure it contains month names
        if (' – ' in text or ' to ' in text) and any(month in text.lower() for month in MONTH_TO_NUM_DICT.keys()):
            event_dates = text.replace(' to ', ' – ').replace('th', '').replace('rd', '').replace('nd', '').replace('1st', '1').replace(',', '').replace('beginning ', '').replace('show dates: ', '')
            break

    # Get event description
    try:
        event_description = p_elements[0].text.strip().replace('\n', ' ')
    except IndexError:
        event_description = None

    # Get image link
    img_container = soup.find('div', class_='ngg-gallery-thumbnail')
    image_link = None
    if img_container:
        first_link_tag = img_container.find('a')
        if first_link_tag:
            image_link = first_link_tag.get('href')

    return event_dates, event_description, image_link

def convert_date_to_nums(date_string):
    """Takes a date in string form and converts it to ints"""
    try:
        date_parts = date_string.strip().split()
        if not date_parts:
            return None, None
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1])
        return month_num, day
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"Error converting date string '{date_string}': {str(e)}")
        return None, None

def scrape_sfwomenartists(env='prod', region='sf'):
    """Scrape and process events from San Francisco Women Artists Gallery."""
    
    # Declare url
    url = 'https://www.sfwomenartists.org/exhibitions/'
    
    # Scrape info and collect events
    soup = fetch_and_parse(url)
    
    # Get google maps link for venue
    gmaps_link = soup.find('p').find('a')['href'].strip()
                
    # Find all events
    events_list = soup.find_all(class_='exhibition-item')

    # Check if events is found
    if events_list:
        for event in events_list:
            # Extract title and title-link
            event_title = event.find('h4', class_='gallery-title').text.strip()
            event_link = event.find('a')['href'].strip()
            
            # Scrape additional info from event url
            event_dates, event_description, image_link = scrape_event_specific_page(event_link)
            # Skip to the next event if end date does not exist
            if not event_dates:
                logging.warning(f"No valid dates found for event: {event_title} at {event_link}")
                continue
            
            # Handle edge cases
            if event_dates == 'august 10 2020':
                event_dates = 'august 10 2020 – august 31 2020'
            elif event_dates == 'september 1 – 25 2020':
                event_dates = 'september 1 2020 – september 25 2020'
            elif event_dates == 'october 2024 exhibition':
                event_dates = 'october 8 2024 – november 1 2024'
            elif event_dates == 'november 5 – 30 2019':
                event_dates = 'november 5 2019 – november 30 2019'

            # Extract date information
            dates = [d.strip() for d in event_dates.split('–')]
            start_date_month, start_date_day = convert_date_to_nums(dates[0])
            if start_date_month is None or start_date_day is None:
                logging.warning(f"Could not parse start date from '{dates[0]}' for event: {event_title}")
                continue
                            
            # If no end month, use the start month
            if len(dates[1].split(' ')) == 1:
                end_date_month = start_date_month
                end_date_day = int(dates[1])
            else:
                if event_dates == 'august 3 – 27 2021':
                    end_date_month = 8
                    end_date_day = 27
                elif event_dates == 'june 1 – 25 2021':
                    end_date_month = 6
                    end_date_day = 25
                else:
                    end_date_month, end_date_day = convert_date_to_nums(dates[1])
                    if end_date_month is None or end_date_day is None:
                        logging.warning(f"Could not parse end date from '{dates[1]}' for event: {event_title}")
                        continue

            try:
                year = int(event.find('p').text.split(' ')[-1])
            except (ValueError, IndexError):
                logging.warning(f"Could not parse year for event: {event_title}")
                continue
            
            if start_date_month and start_date_day and year:
                start_date = dt.date(year, start_date_month, start_date_day)
            else:
                start_date = None
            
            if end_date_month and end_date_day and year:
                # If the end date is in the next year, set it to the next year
                if start_date_month == 12 and end_date_month == 1:
                    year += 1
                end_date = dt.date(year, end_date_month, end_date_day)
            else:
                end_date = None
                
            # Identify phase
            today = dt.datetime.today().date()
            if (start_date != None) and (end_date != None):
                if (start_date <= today) and (end_date >= today):
                    phase = 'current'
                elif (start_date > today) and (end_date > today):
                    phase = 'future'
                elif (start_date < today) and (end_date < today):
                    phase = 'past'
            else:
                phase = None

            event_details = {
                'name': event_title,
                'venue': 'San Francisco Women Artists Gallery',
                'description': event_description,
                'tags': ['exhibition'] + [phase] + ['gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
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
            
            # Add debug logging for dev environment
            if env == 'dev':
                logging.info(f"Event found: {event_details.get('name')} at {event_details.get('venue')}")
            
            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)

    else:
        logging.warning(f"Events not found for San Francisco Women Artists Gallery")