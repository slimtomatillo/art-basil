# Imports
import json
import requests
from bs4 import BeautifulSoup
from hashlib import md5
import datetime as dt
import numpy as np
from unicodedata import normalize
import pandas as pd
import os
import time

DB_FILE = 'docs/events_db.json'
EVENT_TAGS = ['exhibition', 'free']

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
    
    return

def load_db():
    """Load the event database from a JSON file."""
    try:
        with open(DB_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
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
        print(f"Error fetching {url}: {e}")
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

    if event_id not in site_events or site_events[event_id]['hash'] != event_hash:
        print(f"Updating event: {event_details['name']}")
        site_events[event_id] = {**event_details, 'hash': event_hash}
        db[event_details['venue']] = site_events
        save_db(db)
    else:
        print(f"No changes detected for event: {event_details['name']}")

def scrape_de_young_and_legion_of_honor():
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
                    
                    # Identify phase and date fields
                    if date.lower().split()[0] == 'through':
                        # Get phase
                        phase = 'current'
                        # Get dt versions of start and end dates
                        start_date = 'null'
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
                        'links': [
                            {
                                'link': link,
                                'description': 'Event Page'
                            },
                        ],
                    }
                    # Add image link if it exists
                    if image_link:
                        event_details['links'].append({
                            'link': image_link,
                            'description': 'Image'
                        })

                    process_event(event_details)

def scrape_sfmoma():
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
    
    # Go through and collect events in each phase (current, future, and past)
    for phase_dict in divs:

        # Assuming the events container has direct children that are event elements
        events_container = soup.find('div', id=phase_dict['id'])

        # Check if events_container is found
        if events_container:
            # Find all direct child divs that are assumed to represent individual events
            individual_events = events_container.find_all('a', class_='exhibitionsgrid-wrapper-grid-item')

            # Iterate through events and extract details
            for event in individual_events:
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
                # Get start date and end date
                if event_date in ('new exhibition! now on view', 'ongoing'):
                    start_date = 'null'
                    end_date = 'null'
                elif event_date.split()[0] == 'closing':
                    start_date = 'null'
                    end_date = convert_date_to_dt(event_date.replace('closing ', '').replace(',', ''))
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
                            end_date = 'null'
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
                        print(f'No commas found in: {event_date}')
                else:
                    start_date = 'null'
                    end_date = 'null'

                event_image_url = event.find("img", class_="exhibitionsgrid-wrapper-grid-item-image")['src']

                event_details = {
                    'name': event_title,
                    'venue': 'SFMOMA',
                    'description': event_description,
                    'tags': ['exhibition'] + [phase_dict['phase']] + ['museum'],
                    'phase': phase_dict['phase'],
                    'dates': {'start': start_date, 'end': end_date},
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

                }

                process_event(event_details)

        else:
            print(f"Events container not found for phase: {phase_dict['phase']}")

def scrape_cjm():
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
                if event_dates == 'Ongoing exhibit':
                    start_date = 'null'
                    end_date = 'null'
                else:
                    start_date = convert_date_to_dt(dates[0])
                    end_date = convert_date_to_dt(dates[1])
                
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
                    'links': [
                        {
                            'link': event_link,
                            'description': 'Event Page'
                        },
                    ]
                }
                # Add image link if it exists
                if image_link:
                    event_details['links'].append({
                        'link': image_link,
                        'description': 'Image'
                    })

                process_event(event_details)

        else:
            print(f"Events not found for phase: {url_dict['phase']}")

def scrape_sfwomenartists(verbose=True):
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

            # Extract date information
            dates = [d.strip() for d in event_dates.split('–')]
            try:
                start_date_month, start_date_day = convert_date_to_nums(dates[0])
            except KeyError:
                if verbose:
                    print("Error processing start date:", event_dates, event_link)
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
                            print("Error processing end date:", event_dates, event_link)
                        continue  # Skip to the next event if end date conversion fails
            year = int(event.find('p').text.split(' ')[-1])
            
            if start_date_month and start_date_day and year:
                start_date = dt.date(year, start_date_month, start_date_day)
            else:
                start_date = 'null'
            
            if end_date_month and end_date_day and year:
                end_date = dt.date(year, end_date_month, end_date_day)
            else:
                end_date = 'null'
                
            # Identify phase
            today = dt.datetime.today().date()
            if (start_date != 'null') and (end_date != 'null'):
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
                'links': [
                    {
                        'link': event_link,
                        'description': 'Event Page'
                    },
                ]
            }
            # Add image link if it exists
            if image_link:
                event_details['links'].append({
                    'link': image_link,
                    'description': 'Image'
                })
            
            process_event(event_details)

    else:
        print(f"Events not found for San Francisco Women Artists Gallery")

def scrape_asian_art_museum_current_events():
    
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

        # Extract date label
        event_date = featured_event.find(class_='hero-card__aside').find('span').text.lower()
        start_date = 'null'
        if event_date:
            end_date = convert_date_to_dt(event_date)
        else:
            end_date = 'null'

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
            'tags': ['exhibition'] + ['current'] + ['museum'],
            'phase': ['current'],
            'dates': {'start': start_date, 'end': end_date},
            'links': [
                {
                    'link': event_link,
                    'description': 'Event Page'
                },
            ]
        }
        # Add image link if it exists
        if image_link:
            event_details['links'].append({
                'link': image_link,
                'description': 'Image'
            })

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
                image_link = event.find(class_='card__img').find('a')['href']
            except AttributeError:
                image_link = None

            # Extract date label
            event_date = event.find('div', class_='card__subtitle').text.strip().lower().replace('through ', '')
            start_date = 'null'
            if event_date == 'ongoing':
                end_date = 'null'
            elif event_date:
                end_date = convert_date_to_dt(event_date)
            else:
                end_date = 'null'

            # Extract description
            description_tag = event.find('div', class_='card__body')
            event_description = description_tag.get_text(separator='\n').strip() if description_tag else None

            event_details = {
                'name': event_title,
                'venue': 'Asian Art Museum',
                'description': event_description,
                'tags': ['exhibition'] + ['current'] + ['museum'],
                'phase': ['current'],
                'dates': {'start': start_date, 'end': end_date},
                'links': [
                    {
                        'link': event_link,
                        'description': 'Event Page'
                    },
                ]
            }
            # Add image link if it exists
            if image_link:
                event_details['links'].append({
                    'link': image_link,
                    'description': 'Image'
                })

            process_event(event_details)

def main(copy_db=True, record_db_size=True):
    """
    Function that:
        1. Saves a copy of existing data if copy_db=True
        2. Scrapes data from the de Young Museum & Legion of Honor
        3. Scrapes data from SFMOMA
        4. Scrapes data from Contemporary Jewish Museum (CJM)
        5. Scrapes data from SF Women Artists Gallery
        6. Scrapes data from Asian Art Museum
        7. Saves data as json
        8. Records the size of the db (num venues and events) if record_db_size=True
    """
    if copy_db:
        # Save a copy of existing json data
        try:
            copy_json_file('docs/events_db.json', 'docs/events_db_copy.json')
        except FileNotFoundError:
            pass

    # Set start time to measure execution time
    start_time = time.time()

    venue = "de Young & Legion of Honor"
    print(f"Starting scrape for {venue}")
    scrape_de_young_and_legion_of_honor()
    print(f"Finished scrape for {venue}")

    venue = 'SFMOMA'
    print(f"Starting scrape for {venue}")
    scrape_sfmoma()
    print(f"Finished scrape for {venue}")

    venue = 'Contemporary Jewish Museum // CJM'
    print(f"Starting scrape for {venue}")
    scrape_cjm()
    print(f"Finished scrape for {venue}")

    venue = 'San Francisco Women Artists Gallery'
    print(f"Starting scrape for {venue}")
    scrape_sfwomenartists(verbose=False)
    print(f"Finished scrape for {venue}")

    venue = 'Asian Art Museum'
    print(f"Starting scrape for {venue}")
    scrape_asian_art_museum_current_events()
    print(f"Finished scrape for {venue}")

    # Load db and count the venues and events
    db = load_db()
    # Flatten the db into a list of event dictionaries
    events_list = []
    for category in db.values():
        for event in category.values():
            events_list.append(event)
    print('The db contains {:,} venues, with {:,} events'.format(len(db), len(events_list)))

    # Measure execution time of scraping
    execution_time_s = round(time.time() - start_time, 1)
    print(f'Scraping took {execution_time_s} seconds')

    if record_db_size:
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
    
    print('Finished')

if __name__ == "__main__":
    main()
