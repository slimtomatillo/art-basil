from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_string):
    """Converts a date in string form to a dt.date object."""
    date_parts = date_string.lower().split()
    if len(date_parts) == 3:
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1].replace(',', ''))
        year = int(date_parts[2])
        return dt.date(year, month_num, day)
    else:
        return None

def scrape_museum_of_craft_and_design_exhibitions(env='prod', region='sf'):
    """Scrape and process exhibitions from the Museum of Craft and Design."""
    
    def process_exhibitions(url, phase, class_name):
        """Process exhibitions from the given URL for the specified phase."""
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping Museum of Craft and Design {phase} exhibitions --> no soup found")
            return

        exhibition_list = soup.find_all('div', class_=class_name)

        for exhibition in exhibition_list:
            # Get title and link
            title_tag = exhibition.find('h4')
            event_title = title_tag.text.strip().title() if title_tag else None
            event_link = exhibition.find('a')['href'] if exhibition.find('a') else None

            # Extract date information
            if class_name == 'colcustom1':
                date_tag = exhibition.find('h4').find_next('h4')
            else:
                date_tag = exhibition.find('p')
            if date_tag:
                event_dates = date_tag.text.strip().lower().replace(',', '').replace(' – ', '-').replace('–', '-').replace('.', '')
                ongoing = 'ongoing' in event_dates
                
                # Handle edge cases
                if event_dates == 'october 2004 - january 2005':
                    event_dates = 'october 1 2004-january 31 2005'
                                                
                # Split dates by the '-' character for ranges
                if '-' in event_dates:
                    dates = event_dates.split('-')
                    # Handle cases with complete start and end dates
                    if len(dates[0].split()) == 3 and len(dates[1].split()) == 3:
                        start_date = convert_date_to_dt(dates[0])
                        end_date = convert_date_to_dt(dates[1])
                    # Handle cases where the start date is missing the year but the end date has it
                    elif len(dates[0].split()) == 2 and len(dates[1].split()) == 3:
                        start_date = convert_date_to_dt(dates[0] + ' ' + dates[1].split()[-1])  # Append year from end date
                        end_date = convert_date_to_dt(dates[1])
                    # Handle cases where the start and end dates share the same year
                    elif len(dates[0].split()) == 2 and len(dates[1].split()) == 2:
                        shared_year = dt.datetime.now().year  # Default to the current year if not specified
                        start_date = convert_date_to_dt(dates[0] + ' ' + str(shared_year))
                        end_date = convert_date_to_dt(dates[1] + ' ' + str(shared_year))
                else:
                    # Single date case (assuming it might be an opening date)
                    start_date = convert_date_to_dt(event_dates)
                    end_date = None
            else:
                start_date, end_date, ongoing = None, None, False
                                
            # Get description
            try:
                description_element = exhibition.find('div', class_='exitem2').find('p')
                description_text = description_element.get_text().strip() if description_element else None
            except:
                description_text = None
            
            # Extract image if available
            img_tag = exhibition.find('img')
            if img_tag:
                image_link = img_tag['src']
                if image_link.startswith('data:image/gif'):
                    image_link = img_tag['data-src']
            else:
                image_link = None
                        
            event_details = {
                'name': event_title,
                'venue': 'Museum of Craft and Design',
                'description': description_text,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}] if event_link else [],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'prod':
                process_event(event_details, region)

    # Scrape current exhibitions
    process_exhibitions('https://sfmcd.org/exhibitions/', 'current', 'colcustom1')

    # Scrape upcoming exhibitions
    process_exhibitions('https://sfmcd.org/upcoming-exhibitions/', 'future', 'colcustom2')

    # Scrape past exhibitions
    process_exhibitions('https://sfmcd.org/past-exhibitions/', 'past', 'colcustom4')
