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

def scrape_de_young_and_legion_of_honor(env='prod'):
    """Scrape and process events from the de Young and Legion of Honor."""

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