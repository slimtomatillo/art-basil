# Imports
import pandas as pd
import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import datetime as dt

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
        json.dump(data, destination_json_file, indent=4)  # You can use indent for pretty formatting if desired
    
    return

def save_json_file(data, file_path):
    # Step 1: Create or open the destination JSON file and write the data to it
    with open(file_path, 'w') as json_file:
        # Write the data to the destination file
        json.dump(data, json_file, indent=4)  # You can use indent for pretty formatting if desired

def standardize_text(string):
    """
    Initially designed for handling strings containing times.
    Removes periods, lowercases it, and removes spaces.
    """
    # Remove punctuation
    string = string.replace('.', '')

    # Lowercase
    string = string.lower()

    # Remove spaces
    string = string.replace(' ', '')

    # Replace noon with 12
    string = string.replace('noon', '12pm')
    
    return string

def parse_time_to_timestamp(time_str):
    """
    Given a string containing time(s), extract the time
    in the string and convert it to HH:MM form (with :MM
    optional), and specifying am or pm.
    """

    # Regular expression pattern to match time formats
    time_pattern = r'(\d{1,2}(?::\d{2})?)\s?(am|pm)?'

    # Match the time components
    match = re.match(time_pattern, time_str, re.IGNORECASE)
    if match:
        # Extract hours and minutes
        hours_minutes = match.group(1)
        am_pm = match.group(2)

        if am_pm:
            am_pm = am_pm.lower()

        # Convert hours to 24-hour format if needed
        if ':' in hours_minutes:
            hours, minutes = hours_minutes.split(':')
            if am_pm == 'am':
                hours = str(int(hours))
                time_str = f'{hours}:{minutes}'
            elif am_pm == 'pm':
                hours = str(int(hours) + 12)
                time_str = f'{hours}:{minutes}'
        elif ':' not in hours_minutes:
            hours = hours_minutes
            if am_pm == 'am':
                if int(hours) == 12:
                    time_str = '00:00'
                elif len(hours) == 1:
                    hours = hours.zfill(2)
                    time_str = f'{hours}:00'
                else:
                    time_str = f'{hours}:00'
            elif am_pm == 'pm':
                if int(hours) == 12:
                    time_str = f'{hours}:00'
                else:
                    hours = str(int(hours) + 12)
                    time_str = f'{hours}:00'

        # Convert the time string to a datetime timestamp
        try:
            timestamp = datetime.strptime(time_str, '%H:%M').time()
            return timestamp
        except ValueError:
            return None

    return None

def get_sorting_index(date, start_time, end_time):
    """
    Use the date to sort if we have that. Use the time also
    (start time if available otherwise end time) if we have that.

    Expects date in the form YYYY-MM-DD 00:00:00.
    Expects dater_time in the the form HHam/pm or Ham/pm.
    """
    time_sort = None
    
    # If we have the date, use it as the sorting index
    if date:
        time_sort = date

        # These are potential formats the times could be in
        formats = ['%I%p', '%I:%M%p', '%I%P', '%I:%M%P']
            
        # If we have the start time, use that to sort also
        if start_time:
            for fmt in formats:
                try:
                    # Try to parse time with current format
                    parsed_time = datetime.strptime(start_time, fmt).time()
                    time_sort = datetime.combine(time_sort, parsed_time)
                except ValueError:
                    # If parsing fails, continue to next format
                    continue
        
        # Otherwise use the end time if we have it
        elif end_time:
            for fmt in formats:
                try:
                    # Try to parse time with current format
                    parsed_time = datetime.strptime(end_time, fmt).time()
                    time_sort = datetime.combine(time_sort, parsed_time)
                except ValueError:
                    # If parsing fails, continue to next format
                    continue

    return time_sort

def get_de_young_events():
    """
    Uses BeautifulSoup to scrape event info from the de Young
    Museum and Legion of Honor's calendar.
    """
    print("Collecting events from the de Young & Legion of Honor...")

    # Collect event info
    events_list = []

    # Iterate through the pages
    for i in range(1, 10):

        url = "https://www.famsf.org/calendar" + f"?page={i}"
    
        # Send a GET request to fetch the webpage content
        response = requests.get(url)
        html_content = response.content
        
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find elements a class
        group_elements = soup.find_all(class_="mt-24 xl:mt-32")

        # If no pages left, exit loop
        if len(group_elements) == 0: # this will be 0 when we've gone through all the pages
            break
        
        for e in group_elements:
            
            # Extract title
            title = e.find("a").find("h3").get_text().strip()
            
            # Extract link
            link = e.find("a").get("href")
            
            # Extract date info
            date = e.find(class_="mt-12 text-secondary f-subheading-1").get_text()

            def extract_time(string):

                # Standardize string
                string = standardize_text(string)
                
                # If there is \\ in it, there's a time
                if '\\' in string:
                
                    # Split by \\ and choose [-1], then by , and choose [0], and remove spaces
                    string = string.split('\\')[-1].split(',')[0].replace(' ', '')
                    
                    # If a hyphen ("–") is in it, there is a start and end time, split by dash
                    if '–' in string:
                        start_time = string.split('–')[0]
                        end_time = string.split('–')[1]
                
                    # Elif a + is in it, there are two start times, split by +
                    elif '+' in string:
                        start_time = string.split('+')[0]
                        end_time = None
                    
                    # Otherwise
                    else:
                        start_time = string
                        end_time = None

                else:
                    start_time = None
                    end_time = None

                return start_time, end_time

            # Extract time
            start_time, end_time = extract_time(date)

            # Extract venue
            try:
                venue = e.find(class_="text-inherit pt-2 ml-8").get_text()
            except AttributeError:
                venue = "unknown"
            
            # Add tags
            tags = []
            event_type = e.find(class_="text-inherit pt-2").get_text().lower() # this is Exhibition or Event
            if event_type == "exhibition":
                tags.append("exhibition")
            if "tour" in title.lower():
                tags.append("tour")
            if "family" in title.lower():
                tags.append("family")
            if "youngster" in title.lower():
                tags.append("family")
            if "reading" in title.lower():
                tags.append("reading")
            if "concert" in title.lower():
                tags.append("audio")
            if "song bath" in title.lower():
                tags.append("audio")
            if "workshop" in title.lower():
                tags.append("workshop")
            if "free" in title.lower():
                tags.append("free")
            if "opening" in title.lower():
                tags.append("opening")
            if "member" in title.lower():
                tags.append("members only")
            if "symposium" in title.lower():
                tags.append("symposium")
            if "lecture" in title.lower():
                tags.append("talk")
            if "talk" in title.lower():
                tags.append("talk")
            if "conversation" in title.lower():
                tags.append("talk")
            if "party" in title.lower():
                tags.append("party")
            if "queer" in title.lower():
                tags.append("queer")
            if "virtual" in title.lower():
                tags.append("virtual")
            
            # Collect data
            events_list.append(
                {
                    "Title": title,
                    "Links": [{
                        "Link": link,
                        "Text": "Event Page",
                    }],
                    "Date": date,
                    "StartTime": start_time,
                    "EndTime": end_time,
                    "Venue": venue,
                    "Tags": list(set(tags)) # get unique list of tags
                }
            )

    print("Completed. Collected {:,} events.".format(len(events_list)))
    return events_list

def get_berkeley_art_center_events():
    """
    Uses BeautifulSoup to scrape event info from Berkeley Art 
    Center's calendar.
    """
    print("Collecting events from Berkeley Art Center...")
    
    # Collect event info
    events_list = []
    
    # URL of the website to scrape
    url = "https://www.berkeleyartcenter.org/calendar"
    
    # Send a GET request to fetch the webpage content
    response = requests.get(url)
    html_content = response.content
    
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # We'll use this later to identify dates
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    # Get elements
    elements = soup.find_all(class_="col sqs-col-6 span-6")

    # Iterate through elements
    for e in elements:
        
        # If looking at past events, stop the loop
        if "past events" in e.find_previous("h1").text.lower():
            break
        
        # Otherwise, we're looking at current events --> collect events
        else:
            h3s = e.find_all("h3")
            
            # If there are any h3 elements
            if len(h3s) > 0:
                
                # Identify title
                title = h3s[0].get_text().strip()

                # Tag events and collect dates
                dates = []
                tags = []
                # Iterate through h3 elements
                for h in h3s:
                    if any(x in h.get_text().lower() for x in days_of_week):
                        dates.append(h.get_text().strip())
                    if "opening" in h.get_text().lower():
                        tags.append("opening")
                    if "conversation" in h.get_text().lower():
                        tags.append("talk")
                    if "talk" in h.get_text().lower():
                        tags.append("talk")
                    if "dialogue" in h.get_text().lower():
                        tags.append("talk")
                    if "performance" in h.get_text().lower():
                        tags.append("performance")
                    if "workshop" in h.get_text().lower():
                        tags.append("workshop")
                    if "party" in h.get_text().lower():
                        tags.append("party")
                    if "queer" in h.get_text().lower():
                        tags.append("queer")
                    if "virtual" in h.get_text().lower():
                        tags.append("virtual")
                    if "zoom" in h.get_text().lower():
                        tags.append("virtual")

                def extract_date_to_timestamp(s):
                    """
                    Extracts a date from a given string and converts it to a timestamp.
                    
                    The function searches for a date in the format "day of the week, month day, year"
                    within the provided string. The ", year" portion is optional. If the year is not
                    specified, the current year is assumed.
                    """
                    
                    pattern = r'\b(?P<weekday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s(?P<day>\d{1,2})(,\s(?P<year>\d{4}))?\b'
                    
                    match = re.search(pattern, s, re.IGNORECASE)
                    if match:
                        # Extract components
                        month = match.group("month")
                        day = int(match.group("day"))
                        year = int(match.group("year")) if match.group("year") else datetime.now().year
                        
                        # Convert to datetime object (and then back to string so it's json-serializable)
                        dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                        return dt
                    
                    return None
                
                # Combine dates and extract date
                date_str = " | ".join([d.replace('.', '').replace('–', '-').replace('-', '-').replace(' from', ',') for d in dates])
                date_text = date_str # copy date text to use for tags
                date_str = date_str.replace(" on zoom.", "")
                date_display_text = ' '.join([word if word in [None] else word.capitalize() for word in date_str.split()]) # include words in list if we don't want to capitalize them
                date = extract_date_to_timestamp(date_str)
                
                # Identify location
                try:
                    "berkeley art center" in h3s[2].get_text().lower()
                    venue = h3s[2].get_text()
                except IndexError:
                    venue = "Berkeley Art Center"
                else:
                    venue = "Berkeley Art Center"
                if "on zoom" in date_text.lower():
                    venue = "Virtual"
                
                # Get links
                links = []
                link_elements = e.find_all("a")
                if len(link_elements) > 0:
                    for l in link_elements:
                        link_url = l.get("href")
                        if "eventbrite" in link_url.lower():
                            links.append({
                                "Link": link_url,
                                "Text": "Eventbrite"
                            })
                        elif ("berkeleyartcenter" in link_url.lower() and link_url.lower() != "https://www.berkeleyartcenter.org/upcoming-exhibitions"):
                            links.append({
                                "Link": link_url,
                                "Text": "Event Page"
                            })
                        else:
                            links.append({
                                "Link": link_url,
                                "Text": "unknown"
                            })
                
                def extract_time(string):
        
                    # Standardize string
                    string = standardize_text(string)
                    string = string.replace('–', '-').replace('-', '-')
                    
                    # If there is a hyphen, that indicates there is a start and end time
                    if '-' in string:
                        # Get start and end times
                        times = string.split('-')
                        start_time = times[0]
                        # Get the start date from the right side of the hyphen
                        try:
                            end_time = times[1]
                        except IndexError:
                            end_time = None
                        # If the end time is AM, then the start time must be AM
                        if 'am' in end_time:
                            start_time += 'am'
                        # If the end time is PM
                        else:
                            # If the hour of the start time is before the hour of the end time, it must be PM
                            if int(start_time) < int(end_time.replace('am', '').replace('pm', '')):
                                start_time += 'pm'
                            # If the hour is after, it must be AM
                            else:
                                start_time += 'am'
                    
                    # If there is no end time / just a start time
                    else:
                        start_time = string
                        end_time = None

                    return start_time, end_time
                
                # Extract time
                start_time, end_time = extract_time(date_str.split(' ')[-1])

                # Get sorting index
                time_sort = get_sorting_index(date, start_time, end_time)

                # Collect event data
                events_list.append(
                    {
                        "Title": title,
                        "Links": links,
                        "Date": date.strftime('%Y-%m-%d %H:%M:%S'),
                        "DateText": date_display_text,
                        "StartTime": start_time,
                        "EndTime": end_time,
                        "TimeSort": None,
                        "Venue": venue,
                        "Tags": list(set(tags)) # get unique list of tags
                    }
                )
    print("Completed. Collected {:,} events.".format(len(events_list)))
    return events_list

def is_event_recurring(event_str):
    """
    Function that takes in a string containing date and time information
    about an event and identifies whether it is a recurring event or not.
    """
    # Check if the string contains "through" (case insensitive)
    if re.search(r'through', event_str, re.IGNORECASE):
        return True

    # Check if the string contains a "–" or "," between two days of the week or abbreviations
    if re.search(r'(\w{3} – \w{3}|\w{3}, \w{3})', event_str):
        return True

    # Check if the string contains a "+" and has more than one day of the week or abbreviations
    if re.search(r'\+\s*(\w{3}|\w{3},)+', event_str):
        return True

    return False

def main():
    """
    Function that:
        1. Saves a copy of existing data
        2. Scrapes data from the de Young Museum & Legion of Honor
        3. Scrapes data from the Berkeley Art Center
        4. Saves data as json
    """

    # Save a copy of existing json data
    try:
        copy_json_file('website/data.json', 'website/data_copy.json')
    except FileNotFoundError:
        pass

    # Instantiate list to collect data
    data = []

    # Scrape data from the de Young Museum & Legion of Honor
    de_young_data = get_de_young_events()
    data += de_young_data

    # Scrape data from the Berkeley Art Center
    berkeley_art_center_data = get_berkeley_art_center_events()
    data += berkeley_art_center_data

    # Save data as json
    save_json_file(data, 'website/data.json')
    print("."*15)
    print("Saved {:,} events.".format(len(data)))

    return

if __name__ == "__main__":
    main()
