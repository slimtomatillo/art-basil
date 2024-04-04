# Imports
import json
import requests
from bs4 import BeautifulSoup
from hashlib import md5
import datetime as dt
import numpy as np
from unicodedata import normalize

DB_FILE = 'website/events_db.json'
EVENT_TAGS = ['exhibition',]

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
                group_elements = soup.find_all(class_="mt-24 xl:mt-32")
                
                # If no pages left, exit loop
                if len(group_elements) == 0: # this will be 0 when we've gone through all the pages
                    break

                for e in group_elements:

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
                        'tags': ['exhibition'] + [phase], # Add phase to list of tags
                        'phase': phase, # Possible phases are past, current, future
                        'dates': {'start': start_date, 'end': end_date},
                        'links': [
                            {
                                'link': link,
                                'description': 'Event Page'
                            },
                        ],
                    }
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
    
    # Scrap info
    soup = fetch_and_parse(url)
    
    # Go through and collect events in each phase (current, future, and past)
    for phase_dict in divs:

        # Assuming the structure is consistent with your provided HTML example
        # and the container 'events' has direct children that are event elements
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

                # Append extracted details to the list
                event_details = {
                    'name': event_title,
                    'venue': 'SFMOMA',
                    'description': event_description,
                    'tags': ['exhibition'] + [phase_dict['phase']],
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

def main():
    """
    Function that:
        1. Saves a copy of existing data
        2. Scrapes data from the de Young Museum & Legion of Honor
        3. Scrapes data from SFMOMA
        4. Saves data as json
    """
    # Save a copy of existing json data
    try:
        copy_json_file('website/events_db.json', 'website/events_db_copy.json')
    except FileNotFoundError:
        pass

    venue = "de Young & Legion of Honor"
    print(f"Starting scrape for {venue}")
    scrape_de_young_and_legion_of_honor()
    print(f"Finished scrape for {venue}")

    venue = 'SFMOMA'
    print(f"Starting scrape for {venue}")
    scrape_sfmoma()
    print(f"Finished scrape for {venue}")

if __name__ == "__main__":
    main()
