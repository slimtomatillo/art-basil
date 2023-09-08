# Imports
import pandas as pd
import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
    
    return string

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
            # Instantiate list to collect tags
            tags = []
            # Extract title
            title = e.find("a").find("h3").get_text().strip()
            # Extract link
            link = e.find("a").get("href")
            # Extract date info
            date = e.find(class_="mt-12 text-secondary f-subheading-1").get_text()
            # Extract venue
            try:
                venue = e.find(class_="text-inherit pt-2 ml-8").get_text()
            except AttributeError:
                venue = "unknown"
            # Add tags
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

    def parse_time_to_timestamp(time_str):
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
            if am_pm == 'pm' and ':' in hours_minutes:
                hours, minutes = hours_minutes.split(':')
                hours = str(int(hours) + 12)
                time_str = f'{hours}:{minutes}'
            elif am_pm == 'am' and ':' not in hours_minutes and len(hours_minutes) <= 2:
                hours = hours_minutes.zfill(2)
                time_str = f'{hours}:00'
            elif am_pm == 'pm' and ':' not in hours_minutes and len(hours_minutes) <= 2:
                hours = str(int(hours_minutes) + 12)
                time_str = f'{hours}:00'
    
            # Convert the time string to a datetime timestamp
            try:
                timestamp = datetime.strptime(time_str, '%H:%M').time()
                return timestamp
            except ValueError:
                return None

        return None
    
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
                # Collect date(s)
                dates = []
                # Identify title
                title = h3s[0].get_text().strip()
                # Collect tags
                tags = []
                # Collect links
                links = []
                # Iterate through h3 elements
                for h in h3s:
                    if any(x in h.get_text().lower() for x in days_of_week):
                        dates.append(h.get_text().strip())
                    # Tag events
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
                # Combined dates
                date = " | ".join(dates)
                date_text = date # copy date text to use for other purpose
                date = date.replace(" on zoom.", "")
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
                # Get link
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
                # // Extract time //
                # Get the last item after the last space and standardize it
                time = standardize_text(date.split(' ')[-1])
                # If there is a hyphen, that indicates there is a start and end time
                if '–' in date:
                    # Get the start date from the left side of the hyphen
                    start_time = time.split('–')[0]
                    # Get the start date from the right side of the hyphen
                    try:
                        end_time = time.split('–')[1]
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
                    start_time = time
                    end_time = None
                # // Identify sorting index //
                # If we have the start time, use that to sort
                if start_time:
                    time_sort = parse_time_to_timestamp(start_time)
                    # Convert the datetime object to a string in a specific format
                    time_sort = time_sort.strftime("%H:%M:%S")
                # Otherwise use the end time if we have it
                elif end_time:
                    time_sort = parse_time_to_timestamp(end_time)
                    # Convert the datetime object to a string in a specific format
                    time_sort = time_sort.strftime("%H:%M:%S")
                # Collect event data
                events_list.append(
                    {
                        "Title": title,
                        "Links": links,
                        "Date": date,
                        "StartTime": start_time,
                        "EndTime": end_time,
                        "TimeSort": time_sort,
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
