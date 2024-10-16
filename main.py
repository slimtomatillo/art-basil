# Imports
import json
import requests
from bs4 import BeautifulSoup
from hashlib import md5
import datetime as dt
from datetime import timezone
import numpy as np
from unicodedata import normalize
import pandas as pd
import os
import time
import logging

DB_FILE = 'docs/events_db.json'

# Create month to month number dict
month_to_num_dict = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
    
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12,
    
    'sept': 8,
}

def configure_logging(env):
    """Configure logging based on the environment."""
    # Clear existing handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Set level to WARNING for console

    handlers = [console_handler]

    if env == 'prod':
        file_handler = logging.FileHandler("scraping.log", mode='a')
        file_handler.setLevel(logging.INFO)  # Set level to INFO for file
        handlers.append(file_handler)
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Set the root logger level to INFO
    root_logger.setLevel(logging.INFO)

def copy_json_file(source_file_path, destination_file_path):
    """
    Function to take the source path of a json file and make
    a copy of the json file to the destination_file_path.
    """
    # Step 1: Open and read the JSON file
    with open(source_file_path, 'r') as json_file:
        # Load the JSON content into a Python data structure
        data = json.load(json_file)

    # Step 2: Create or open the destination JSON file and write the data to it
    with open(destination_file_path, 'w') as destination_json_file:
        # Write the data to the destination file
        json.dump(data, destination_json_file, indent=4)  # Index makes for pretty formatting

    logging.info(f"Copied {source_file_path} to {destination_file_path}")
    
    return

def convert_nan_to_none(data):
    """Recursively convert NaN values to None in a dictionary or list."""
    if isinstance(data, dict):
        return {k: convert_nan_to_none(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_nan_to_none(i) for i in data]
    elif isinstance(data, float) and np.isnan(data):
        return None
    else:
        return data

def load_db():
    """Load the event database from a JSON file."""
    try:
        with open(DB_FILE, 'r') as file:
            db = json.load(file)
            return convert_nan_to_none(db)  # Convert NaNs to None
    except FileNotFoundError:
        logging.warning(f"Database file {DB_FILE} not found.")
        return {}

def save_db(db):
    """Save the event database to a JSON file."""
    with open(DB_FILE, 'w') as file:
        json.dump(db, file, indent=4, default=str)

def fetch_and_parse(url):
    """Fetch content of a webpage and return a BeautifulSoup object."""
    try:
        # Send a GET request to fetch the webpage content
        response = requests.get(url, headers={'User-Agent': 'Your Bot 0.1'})
        response.raise_for_status()
        # Parse the HTML content using BeautifulSoup
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def generate_event_hash(event_details):
    """Generate a hash of the event details to detect changes."""
    event_string = json.dumps(event_details, sort_keys=True, default=str)
    return md5(event_string.encode('utf-8')).hexdigest()

def generate_unique_identifier(event_details):
    """Generate a unique identifier for an event."""
    return f"{event_details['name']}-{event_details['venue']}"

def process_event(event_details):
    """Check if an event is new or has changed and update the database accordingly."""
    db = load_db()
    site_events = db.get(event_details['venue'], {})
    
    event_id = generate_unique_identifier(event_details)
    event_hash = generate_event_hash(event_details)

    # If event needs to be updated / changes were detected
    if event_id not in site_events or site_events[event_id]['hash'] != event_hash:
        logging.info(f"Updating event: {event_details['name']}")
        site_events[event_id] = {**event_details, 'hash': event_hash}
        db[event_details['venue']] = site_events
        save_db(db)

def scrape_de_young_and_legion_of_honor(env='prod'):
    """Scrape and process events from the de Young and Legion of Honor."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        year = int(date_parts[2])
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

    # Declare list of url dicts and then iterate through them
    urls = [
        {
            'venue': 'de Young',
            'base_url': 'https://www.famsf.org/calendar?type=exhibition&location=de-young'
        },
        {
            'venue': 'Legion of Honor',
            'base_url': 'https://www.famsf.org/calendar?type=exhibition&location=legion-of-honor'
        },
        {
            'venue': 'Virtual',
            'base_url': 'https://www.famsf.org/calendar?type=exhibition&location=virtual'
        }
    ]
    for u in urls:
        # Iterate through the pages
        for i in range(1, 10):
            if i == 1:
                url = u['base_url']
            else:
                url = u['base_url'] + f"?page={i}"
            soup = fetch_and_parse(url)
            if soup:
                # Find elements a class
                group_elements = soup.find_all(class_="flex flex-col-reverse")
                
                # If no pages left, exit loop
                if len(group_elements) == 0: # this will be 0 when we've gone through all the pages
                    break

                for element in group_elements:
                    try:
                        # Get image link if possible
                        pics = element.find_all("picture")
                        source_tag = pics[1].find('source')
                        # Assuming srcset is found
                        if source_tag and source_tag.has_attr('srcset'):
                            srcset_value = source_tag['srcset']
                            srcset_list = srcset_value.split(', ')
                            urls = [item.split(' ')[0] for item in srcset_list]
                            # Get biggest image
                            image_link = urls[-1]
                        else:
                            image_link = None
                                                
                        e = element.find(class_="mt-24 xl:mt-32")

                        # Extract name
                        name = e.find("a").find("h3").get_text().strip()

                        # Extract link
                        link = e.find("a").get("href")

                        # Extract date info
                        date = e.find(class_="mt-12 text-secondary f-subheading-1").get_text()
                        ongoing = True if date.lower() == 'ongoing' else False
                        
                        # Identify phase and date fields
                        if date.lower().split()[0] == 'through':
                            # Get phase
                            phase = 'current'
                            # Get dt versions of start and end dates
                            start_date = None
                            dates = [date.lower().replace(',', '').replace('through ', '')]
                            end_date = convert_date_to_dt(dates[0])

                        else:
                            # Get phase
                            phase = 'future'
                            # Get dt versions of start and end dates
                            dates = date.lower().replace(',', '').split(' – ')
                            # If no year in the date, add the year (use year of end date)
                            if len(dates[0].split()) == 2:
                                dates[0] = dates[0] + ' ' + dates[1].split()[-1]
                            start_date = convert_date_to_dt(dates[0])
                            end_date = convert_date_to_dt(dates[1])
                                                
                        event_details = {
                            'name': name,
                            'venue': u['venue'],
                            'tags': ['exhibition'] + [phase] + ['museum'],
                            'phase': phase, # Possible phases are past, current, future
                            'dates': {'start': start_date, 'end': end_date},
                            'ongoing': ongoing,
                            'links': [
                                {
                                    'link': link,
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

                    except Exception as e:
                        logging.error(f"Error processing element for {u['venue']}: {e}", exc_info=True)

def scrape_sfmoma(env='prod'):
    """Scrape and process events from SFMOMA."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        year = int(date_parts[2])
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt
    
    # Declare url
    url = 'https://www.sfmoma.org/exhibitions/'

    # Declare list of div ids
    divs = [
        {
            'id': 'item--exhibitions-current',
            'phase': 'current'
        },
        {
            'id': 'item--exhibitions-upcoming',
            'phase': 'future'
        },
        {
            'id': 'item--exhibitions-past',
            'phase': 'past'
        }
    ]
    
    # Scrape info
    soup = fetch_and_parse(url)
    if not soup:
        logging.error("Failed to fetch SFMOMA exhibitions page")
        return
    
    # Go through and collect events in each phase (current, future, and past)
    for phase_dict in divs:

        # Assuming the events container has direct children that are event elements
        events_container = soup.find('div', id=phase_dict['id'])
        
        if not events_container:
            logging.warning(f"Events container not found for phase: {phase_dict['phase']}")
            continue

        # Find all direct child divs that are assumed to represent individual events
        individual_events = events_container.find_all('a', class_='exhibitionsgrid-wrapper-grid-item')

        # Iterate through events and extract details
        for event in individual_events:
            try:
                # Event link
                event_link = event['href']

                # Title
                event_title = event.find("div", class_="exhibitionsgrid-wrapper-grid-item-text-title").text.strip()

                # Floor in SFMOMA - unique to SFMOMA
                event_floor = normalize('NFKD', event.find("span", class_="exhibitionsgrid-wrapper-grid-item-location").text.strip())

                # Description
                try:
                    event_description = event.find("div", class_="exhibitionsgrid-wrapper-grid-item-text-desc").text.strip()
                except AttributeError:
                    event_description = ''

                # Dates
                event_date = event.find("div", class_="exhibitionsgrid-wrapper-grid-item-text-date").text.strip().lower()
                event_date = event_date.split('member previews')[0]
                # Replace seasons with estimated dates
                if 'fall' in event_date:
                    event_date = event_date.replace('fall', 'sep 20,')
                if 'winter' in event_date:
                    event_date = event_date.replace('winter', 'dec 20,')
                if 'spring' in event_date:
                    event_date = event_date.replace('spring', 'mar 20,')
                if 'summer' in event_date:
                    event_date = event_date.replace('summer', 'jun 20,')
                # Mark 'ongoing' flag
                ongoing = True if 'ongoing' in event_date else False
                # Get start date and end date
                if event_date in ('new exhibition! now on view', 'ongoing'):
                    start_date = None
                    end_date = None
                elif event_date.split()[0] == 'closing':
                    start_date = None
                    end_date = convert_date_to_dt(event_date.replace('closing ', '').replace(',', ''))
                elif event_date.split()[0] == 'opening':
                    start_date = convert_date_to_dt(event_date.replace('opening ', '').replace(',', ''))
                    end_date = None
                elif '–' in event_date:
                    dates = event_date.split('–')
                    # If there are two commas, this implies that both dates have a month, day, and year
                    if event_date.count(',') == 2:
                        start_date = convert_date_to_dt(dates[0].replace(',', ''))
                        end_date = convert_date_to_dt(dates[1].replace(',', ''))
                    # If not, this implies either the day or year is missing
                    elif event_date.count(',') == 1:
                        if dates[1] == 'ongoing':
                            start_date = convert_date_to_dt(dates[0].replace(',', ''))
                            end_date = None
                        # The day or year is missing in one of the dates
                        else:
                            # The start date is missing something
                            if len(dates[0].split()) == 2:
                                # Has year, missing day
                                if len(dates[0].split()[1]) == 4:
                                    date_0_rev = dates[0].split()[0] + ' 1 ' + dates[0].split()[1]
                                    start_date = convert_date_to_dt(date_0_rev)
                                # Has day, missing year (use year from end date)
                                else:
                                    date_0_rev = dates[0].split()[0] + ' ' + dates[0].split()[1] + ' ' + dates[1].split()[-1]
                                    start_date = convert_date_to_dt(date_0_rev.replace(',', ''))
                                end_date = convert_date_to_dt(dates[1].replace(',', ''))
                            # The end date is missing something
                            else:
                                # Has year, missing day
                                if len(dates[1].split()[1]) == 4:
                                    date_1_rev = dates[1].split()[0] + ' 1 ' + dates[1].split()[1]
                                    end_date = convert_date_to_dt(date_1_rev)
                                # Has day, missing year (use year from start date)
                                else:
                                    date_1_rev = dates[1].split()[0] + ' ' + dates[1].split()[1] + ' ' + dates[0].split()[-1]
                                    end_date = convert_date_to_dt(date_1_rev.replace(',', ''))
                                start_date = convert_date_to_dt(dates[0].replace(',', ''))
                    else:
                        logging.warning(f"No commas found in: {event_date}")
                        start_date = None
                        end_date = None
                else:
                    start_date = None
                    end_date = None

                event_image_url = event.find("img", class_="exhibitionsgrid-wrapper-grid-item-image")['src']

                event_details = {
                    'name': event_title,
                    'venue': 'SFMOMA',
                    'description': event_description,
                    'tags': ['exhibition'] + [phase_dict['phase']] + ['museum'],
                    'phase': phase_dict['phase'],
                    'dates': {'start': start_date, 'end': end_date},
                    'ongoing': ongoing,
                    'links': [
                        {
                            'link': event_link,
                            'description': 'Event Page'
                        },
                        {
                            'link': event_image_url,
                            'description': 'Image'
                        },
                    ],
                    'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                }

                if env == 'prod':
                    process_event(event_details)

            except Exception as e:
                logging.error(f"Error processing event: {e}", exc_info=True)

def scrape_contemporary_jewish_museum(env='prod'):
    """Scrape and process events from Contemporary Jewish Museum."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        year = int(date_parts[2])
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt
    
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

def scrape_sfwomenartists(env='prod', verbose=False):
    """Scrape and process events from San Francisco Women Artists Gallery."""
    
    def scrape_event_specific_page(event_url):
        """Given the url for a specific event, scrape info"""

        # Scrape info and collect events
        soup = fetch_and_parse(event_url)

        # Find all <p> elements within <header class="article-header">
        p_elements = soup.find('header', class_='article-header').find_all('p')

        # Get date info
        try:
            event_dates = p_elements[1].text.strip().lower().replace(' to ', ' – ').replace('th', '').replace('rd', '').replace('nd', '').replace(',', '').replace('beginning ', '').replace('show dates: ', '')
        except IndexError:
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
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        return month_num, day
    
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
                if verbose:
                    logging.info("Error processing start date:", event_dates, event_link)
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
                        if verbose:
                            logging.info("Error processing end date:", event_dates, event_link)
                        continue  # Skip to the next event if end date conversion fails
            year = int(event.find('p').text.split(' ')[-1])
            
            if start_date_month and start_date_day and year:
                start_date = dt.date(year, start_date_month, start_date_day)
            else:
                start_date = None
            
            if end_date_month and end_date_day and year:
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

def scrape_asian_art_museum_current_events(env='prod'):
    """Scrape and process current events from Asian Art Museum."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        if len(date_parts) == 3:
            year = int(date_parts[2])
        else:
            year = dt.datetime.now().year
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

    # Scrape info
    url = 'https://exhibitions.asianart.org/'
    soup = fetch_and_parse(url)
    
    # Get featured event (formatted differently than other events)
    featured_event = soup.find(class_='hero-card -wrap')

    # Check if featured event was found
    if featured_event:

        # Extract title and title-link
        title_tag = featured_event.find(class_='hero-card__title')
        if title_tag:
            event_title = title_tag.text.strip()
            event_link = title_tag.get('href')
        else:
            event_title, event_link = None, None

        # Extract image link if possible
        try:
            image_link = featured_event.find(class_='hero-card__image-src')['src']
        except TypeError:
            image_link = None

        # Extract date info
        date_element = featured_event.find(class_='hero-card__aside')
        event_date = date_element.find('span').text.lower().strip()
        ongoing = True if event_date == 'ongoing' else False
        phase = 'current'
        if 'open' in date_element.text.lower(): # This implies the date corresponds to the opening date
            start_date = convert_date_to_dt(event_date)
            end_date = None # Ideally scrape the exhibition page to get the end date
            if start_date > dt.datetime.now().date():
                phase = 'future'
        else: # This implies the date correspond to the closing date
            start_date = None
            if event_date:
                end_date = convert_date_to_dt(event_date)
            else:
                end_date = None

        # Extract description
        description_tag = featured_event.find('div', class_='hero-card__desc')
        # Extracting all text within the div
        if description_tag:
            extracted_text = description_tag.get_text(separator=' ', strip=True)
            # Additional string manipulation to correct spacing issues before 's'
            corrected_text = extracted_text.replace(' s ', 's ')
            event_description = corrected_text
        else:
            event_description = None

        event_details = {
            'name': event_title,
            'venue': 'Asian Art Museum',
            'description': event_description,
            'tags': ['exhibition'] + [phase] + ['museum'],
            'phase': phase,
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

    # Find rest of events
    events_list = soup.find_all(class_='card split-grid__card split-grid__card--dark')

    # Check if events were found
    if events_list:

        for event in events_list:
            # Extract title and title link
            title_tag = event.find(class_='card__title')
            if title_tag:
                event_title = title_tag.text.strip()
                event_link = title_tag['href']
            else:
                event_title, event_link = None, None

            # Extract image link if possible
            try:
                image_link = event.find(class_='card__img').find('a').find('img')['src']
            except AttributeError:
                image_link = None

            # Extract date label
            event_date = event.find('div', class_='card__subtitle').text.strip().lower().replace('through ', '')
            ongoing = True if event_date.strip() in ['ongoing', 'now on view'] else False
            start_date = None
            if event_date in ['ongoing', 'now on view']:
                end_date = None
            elif event_date:
                end_date = convert_date_to_dt(event_date)
            else:
                end_date = None

            # Extract description
            description_tag = event.find('div', class_='card__body')
            event_description = description_tag.get_text(separator='\n').strip() if description_tag else None

            # Identify phase
            phase = 'current'

            event_details = {
                'name': event_title,
                'venue': 'Asian Art Museum',
                'description': event_description,
                'tags': ['exhibition'] + [phase] + ['museum'],
                'phase': phase,
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

def scrape_asian_art_museum_past_events(env='prod'):
    """Scrape and process past events from Asian Art Museum."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        if len(date_parts) == 3:
            year = int(date_parts[2])
        else:
            year = dt.datetime.now().year
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

    # Scrape info
    url = 'https://exhibitions.asianart.org/past/'
    soup = fetch_and_parse(url)
    
    # Find rest of events
    wrap_elements = soup.find(class_='exhibit-archive').find(class_='exhibit__content').find_all(class_='-wrap')
    articles = []
    for e in wrap_elements:
        a = e.find_all('article')
        if len(a) > 0:
            articles += a

    # Check if events were found
    if articles:

        for article in articles:

            # Ignore the year cards
            if 'card-slash' not in article['class']:

                # Extract title and title link
                title_tag = article.find('a', class_='card__title')
                if title_tag:
                    event_title = title_tag.text.strip()
                    event_link = title_tag['href']
                else:
                    event_title, event_link = None, None

                # Extract image link if possible
                img_tag = article.find('img', class_='card__img-src')
                if img_tag:
                    image_link = img_tag['src']
                else:
                    image_link = None

                # Extract date information
                date_tag = article.find('div', class_='card__subtitle')
                event_dates = date_tag.text.strip() if date_tag else None
                dates = event_dates.lower().replace(',', '').split('–')
                if event_dates:
                    start_date = convert_date_to_dt(dates[0])
                    end_date = convert_date_to_dt(dates[1])
                else:
                    start_date = None
                    end_date = None

                # Identify phase
                phase = 'past'

                event_details = {
                    'name': event_title,
                    'venue': 'Asian Art Museum',
                    'description': None,
                    'tags': ['exhibition'] + [phase] + ['museum'],
                    'phase': phase,
                    'dates': {'start': start_date, 'end': end_date},
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
                    
def scrape_oak_museum_of_ca_exhibitions(env='prod'):
    """Scrape and process events from the Oakland Museum of California (OMCA)."""
    
    def fetch_event_details(event_url):
        """Fetch and parse details from the event's page."""
        
        def convert_date_to_dt(date_text):
            """Convert date text to a datetime object, determining the year based on the next occurrence."""
            global month_to_num_dict

            # Get current date
            today = dt.date.today()
            current_year = today.year

            # Split the date text
            date_parts = date_text.lower().strip().split()
            month_str = date_parts[0]
            day = int(date_parts[1])

            # Convert month to number
            month = month_to_num_dict[month_str]

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

        event_soup = fetch_and_parse(event_url)
        if not event_soup:
            return None, None, None

        # Find all header tags (h1, h2, h3, h4, h5, h6)
        header_tags = event_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for header in header_tags:
            date_text = header.get_text(strip=True).lower().replace('-', '–') # make dashes the same
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
                # Past exhibition
                elif '–' in date_text:
                    date_text = date_text.replace(',', '').replace('.', '').split(' | ')[0].split(' i ')[0].split('–')
                    start_date = convert_date_to_dt(date_text[0])
                    end_date = convert_date_to_dt(date_text[1]) if len(date_text) > 1 else None
                    ongoing = False
                    return start_date, end_date, ongoing

        # Otherwise, it's a past exhibition
        date_text = event_soup.find('h1', class_='wp-block-post-title').find_next('p')
        if date_text:
            date_text = date_text.get_text(strip=True).lower().replace(',', '').split('–')
            start_date = convert_date_to_dt(date_text[0])
            end_date = convert_date_to_dt(date_text[1]) if len(date_text) > 1 else None
            ongoing = False
            return start_date, end_date, ongoing

        return None, None, False

    url = 'https://museumca.org/on-view/#exhibitions'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.info('Error scraping OMCA exhibitions')
        return

    exhibition_elements = soup.find_all('div', class_='post-tile post-tile_type-on-view')

    for elem in exhibition_elements:
        try:
            # Extract title
            title = elem.find('span', class_='post-tile__title').text.strip()

            # Extract description
            description = elem.find('span', class_='post-tile__excerpt').text.strip().replace('\n', '').replace('\xa0', ' ')

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

            if env == 'prod':
                process_event(event_details)

        except Exception as e:
            logging.warning(f"Error parsing element of url {event_link}: {e}")
            continue

def scrape_kala_exhibitions(env='prod'):
    """Scrape and process exhibitions from the Kala Art Institute."""
    
    def convert_date_to_dt(date_text):
        """Convert date text to a datetime object, determining the year based on the next occurrence."""
        global month_to_num_dict

        # Get current date
        today = dt.date.today()
        current_year = today.year

        # Split the date text
        date_parts = date_text.lower().strip().split()
        month_str = date_parts[0]
        day = int(date_parts[1])

        # Convert month to number
        month = month_to_num_dict[month_str]

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

            if env == 'prod':
                process_event(event_details)

        except AttributeError as e:
            logging.info(f"Error parsing element: {e}")

def scrape_cantor_exhibitions(env='prod'):
    """Scrape and process exhibitions from the Cantor Arts Center at Stanford University."""
    
    # Create dict to map our phases to the ones used by the venue
    phase_dict = {
        'current': 'current',
        'future': 'upcoming',
        'past': 'past',
    }

    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""
        global month_to_num_dict
        
        # Handle 'ongoing'
        if date_string == 'ongoing':
            return None

        date_parts = date_string.split()
        month_num = int(month_to_num_dict[date_parts[0]])
        day = int(date_parts[1])
        year = int(date_parts[2])
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

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

def scrape_bampfa_exhibitions(env='prod'):
    """Scrape and process exhibitions from BAMPFA (Berkeley Art Museum and Pacific Film Archive)."""

    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object."""
        global month_to_num_dict

        date_parts = date_string.lower().split()
        if len(date_parts) == 3:
            month_num = int(month_to_num_dict[date_parts[0]])
            day = int(date_parts[1].replace(',', ''))
            year = int(date_parts[2])
        else:
            return None

        return dt.date(year, month_num, day)

    def process_exhibitions(url, phase):
        """Process exhibitions for a given URL and phase (current, past)."""
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping BAMPFA {phase} exhibitions --> no soup found")
            return

        exhibition_list = soup.find_all('li', class_='exhibition')
        
        for exhibition in exhibition_list:
            title_tag = exhibition.find('h2', class_='caption-txt')
            if title_tag:
                event_title = title_tag.text.strip()
                event_link = title_tag.find('a')['href']
            else:
                event_title, event_link = None, None
                
            # Stop at Eric Baudelaire / MATRIX 257
            if event_title == 'Eric Baudelaire / MATRIX 257':
                break

            # Extract date information
            date_tag = exhibition.find('span', class_='dates')
            if date_tag:
                event_dates = date_tag.text.strip()
                if '–' in event_dates:  # Handles date ranges
                    dates = event_dates.lower().replace(',', '').split('–')
                    # Handle edge cases
                    if event_title == 'On the Outdoor Screen: Navigating the Pilot School':
                        start_date = convert_date_to_dt('march 21 2024')
                        end_date = convert_date_to_dt('april 24 2024')
                    elif event_title == 'The 46th Annual University of California, Berkeley Master of Fine Arts Graduate Exhibition':
                        start_date = convert_date_to_dt('june 29 2016')
                        end_date = convert_date_to_dt('august 7 2016')
                    elif event_title == 'Eric Baudelaire / MATRIX 257':
                        start_date = convert_date_to_dt('february 4 2015')
                        end_date = convert_date_to_dt('february 21 2015')
                    # If year is missing from first date, get year from second date
                    elif len(dates[0].split(' ')) == 2 and len(dates[1].split(' ')) == 3:
                        start_date = convert_date_to_dt(dates[0] + ' ' + dates[1].split(' ')[2])
                        end_date = convert_date_to_dt(dates[1])
                    # If date text is in form April 18–22, 2022
                    elif len(dates[0].split(' ')) == 2 and len(dates[1].split(' ')) == 2:
                        start_date = convert_date_to_dt(dates[0] + ' ' + dates[1].split(' ')[-1])
                        end_date = convert_date_to_dt(dates[0].split(' ')[0] + ' ' + dates[1])
                    else:
                        start_date = convert_date_to_dt(dates[0])
                        end_date = convert_date_to_dt(dates[1])
                else:
                    start_date = convert_date_to_dt(event_dates)
                    end_date = None
            else:
                start_date, end_date = None, None
                
            # Get description
            description_text = None
            description_element = exhibition.find('p')
            if description_element:
                description_text = description_element.get_text()

            # Extract image if available
            img_tag = exhibition.find('img')
            if img_tag:
                image_link = img_tag['src']
            else:
                image_link = None

            event_details = {
                'name': event_title,
                'venue': 'BAMPFA',
                'description': description_text,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'links': [{'link': event_link, 'description': 'Event Page'}],
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

    # Scrape current exhibitions
    current_url = 'https://bampfa.org/on-view/exhibitions?field_event_series_type_value=1'
    process_exhibitions(current_url, 'current')

    # Scrape past exhibitions
    past_url = 'https://bampfa.org/on-view/exhibitions/past'
    process_exhibitions(past_url, 'past')
            
def update_event_phases():
    """
    Load the event database, update the phase and tags of art events based on their end date,
    and save the updated database.

    This function loads the events from the database, checks whether the end date of each event 
    is in the past, and updates the event's "phase", "tags", and "ongoing" status accordingly.
    The updated database is then saved back to the JSON file. This is meant to correct situations
    where the phase indicates the event is current but the end date is in the past.

    Returns:
    None
    """
    
    # Load the event database
    db = load_db()
    
    today = dt.datetime.now().date()

    for venue, events in db.items():
        for event_key, event in events.items():
            try:
                end_date_str = event['dates'].get('end')
                end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str and end_date_str != None else None
                
                if end_date and end_date < today:
                    event['phase'] = 'past'
                    event['ongoing'] = False
                    # Ensure "past" is in tags and "current" is not
                    event['tags'] = [tag for tag in event['tags'] if tag != 'current']
                    if 'past' not in event['tags']:
                        event['tags'].append('past')
                else:
                    # Optional: Reset to current or future based on your needs
                    if 'past' in event['tags']:
                        event['tags'].remove('past')

            except ValueError as e:
                print(f"Error processing event '{event_key}' in venue '{venue}': {e}")
                # Optionally handle or log the error further as needed
    
    # Save the updated database
    save_db(db)

def main(env='prod', selected_venues=None, skip_venues=None,write_summary=True):
    """
    Function that:
        1. Saves a copy of existing data if env='prod'
        2. Scrapes data from selected (list expected) or all venues, skipping those in skip_venues (list expected)
        3. Saves data as json if env='prod'
        4. Records the size of the db (num venues and events) if env='prod' and write_summary=True
    """

    # Configure logging based on the environment parameter
    configure_logging(env)
    logging.info("----------NEW LOG----------")
    
    if env == 'prod':
        # Save a copy of existing json data
        try:
            copy_json_file('docs/events_db.json', 'docs/events_db_copy.json')
        except FileNotFoundError:
            logging.warning('Original events_db.json file not found. No copy created.')

    # Set start time to measure execution time
    start_time = time.time()
    logging.info('Starting the scraping process')

    # Mapping venue names to their respective scraper functions
    venues = {
        "de Young & Legion of Honor": scrape_de_young_and_legion_of_honor,
        "SFMOMA": scrape_sfmoma,
        "Contemporary Jewish Museum (CJM)": scrape_contemporary_jewish_museum,
        "San Francisco Women Artists Gallery": scrape_sfwomenartists,
        # Asian Art Museum requires both current and past events scrapers
        "Asian Art Museum": [scrape_asian_art_museum_current_events, scrape_asian_art_museum_past_events],
        "Oakland Museum of Art (OMCA)": scrape_oak_museum_of_ca_exhibitions,
        "Kala Art Institute": scrape_kala_exhibitions,
        "Cantor Arts Center": scrape_cantor_exhibitions,
        "BAMPFA": scrape_bampfa_exhibitions,
    }

    # Filter the venues based on selected_venues (if provided)
    if selected_venues:
        logging.info(f"Only scraping {selected_venues}")
        venues = {k: v for k, v in venues.items() if k in selected_venues}

    # Filter the venues based on skip_venues (if provided)
    if skip_venues:
        logging.info(f"Skipping {skip_venues}")
        venues = {k: v for k, v in venues.items() if k not in skip_venues}

    for venue, scraper in venues.items():
        # Log the start of scraping for each venue
        logging.info(f"Starting scrape for {venue}")

        if isinstance(scraper, list):
            # If scraper is a list (e.g., multiple functions for a venue), iterate through the list
            for s in scraper:
                s(env=env)
        else:
            # Otherwise, call the single scraper function
            scraper(env=env)
        
        # Log the completion of scraping for each venue
        logging.info(f"Finished scrape for {venue}")

    if env == 'prod' and write_summary:
        # This block runs only when write_summary is True
        # Correct instances of misalignment between phase and end date
        updated_db = update_event_phases()
        
        # Load db and count the venues and events
        db = load_db()
        # Flatten the db into a list of event dictionaries
        events_list = []
        for category in db.values():
            for event in category.values():
                events_list.append(event)
        logging.info("The db contains {:,} venues, with {:,} events".format(len(db), len(events_list)))

        # Measure execution time of scraping
        execution_time_s = round(time.time() - start_time, 1)
        logging.info(f"Scraping took {execution_time_s} seconds")

        # Record the number of venues and events in the db
        file_path = 'docs/db_size.csv'
        df = pd.DataFrame([{
            "timestamp": pd.Timestamp.now(),
            "num_venues": len(db),
            "num_events": len(events_list),
            "scrape_time_s": execution_time_s
        }])
        # Check if the file exists
        if os.path.exists(file_path):
            # File exists, append without writing the header
            df.to_csv(file_path, mode='a', header=False, index=False)
        else:
            # File does not exist, write with the header
            df.to_csv(file_path, mode='w', header=True, index=False)
        logging.info("Database size recorded")
    
    logging.info("Finished")

if __name__ == "__main__":
    main()