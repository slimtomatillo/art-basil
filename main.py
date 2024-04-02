# Imports
import json
import requests
from bs4 import BeautifulSoup
from hashlib import md5
import datetime as dt
import numpy as np

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
    'dec': 12
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
                        phase = 'Current'
                        # Get dt versions of start and end dates
                        start_date = 'null'
                        dates = [date.lower().replace(',', '').replace('through ', '')]
                        end_date = convert_date_to_dt(dates[0])

                    else:
                        # Get phase
                        phase = 'Future'
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
                        'tags': ['exhibition'],
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

def main():
    """
    Function that:
        1. Saves a copy of existing data
        2. Scrapes data from the de Young Museum & Legion of Honor
        3. Saves data as json
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

if __name__ == "__main__":
    main()
