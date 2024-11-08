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
    p_elements = soup.find('header', class_='article-header').find_all('p')

    # Get date info
    try:
        p_text = [e.text for e in p_elements if '–' in e.text]
        event_dates = p_text[0].strip().lower().replace(' to ', ' – ').replace('th', '').replace('rd', '').replace('nd', '').replace(',', '').replace('beginning ', '').replace('show dates: ', '')
    except:
        event_dates = None

    # Get event description
    try:
        event_description = p_elements[0].text.strip().replace('\n', ' ')
    except IndexError:
        event_description = None

    # Get image link
    first_link_tag = soup.find('div', class_='ngg-gallery-thumbnail').find('a')
    # Extract the 'href' attribute from the <a> element
    if first_link_tag:
        image_link = first_link_tag.get('href')
    else:
        image_link = None

    return event_dates, event_description, image_link

def convert_date_to_nums(date_string):
    """Takes a date in string form and converts it to ints"""

    date_parts = date_string.split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    day = int(date_parts[1])
    return month_num, day

def scrape_sfwomenartists(env='prod'):
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
                continue
            
            # Handle edge case
            if event_dates == 'august 10 2020':
                event_dates = 'august 10 – august 31 2020'
            elif event_dates == 'september 1 – 25 2020':
                event_dates = 'september 1 – september 25 2020'
            elif event_dates == 'october 2024 exhibition':
                event_dates = 'october 8 – november 1'

            # Extract date information
            dates = [d.strip() for d in event_dates.split('–')]
            try:
                start_date_month, start_date_day = convert_date_to_nums(dates[0])
            except KeyError:
                logging.warning("Error processing start date:", event_dates, event_link)
                continue  # Skip to the next event if start date conversion fails
                            
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
                    try:
                        end_date_month, end_date_day = convert_date_to_nums(dates[1])
                    except KeyError:
                        logging.warning("Error processing end date:", event_dates, event_link)
                        continue  # Skip to the next event if end date conversion fails
            year = int(event.find('p').text.split(' ')[-1])
            
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
            
            if env == 'prod':
                process_event(event_details)

    else:
        logging.warning(f"Events not found for San Francisco Women Artists Gallery")