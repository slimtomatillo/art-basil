from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_string):
    """Takes a date in string form and converts it to a dt object."""

    date_parts = date_string.lower().split()
    if len(date_parts) == 3:
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1].replace(',', ''))
        year = int(date_parts[2])
    else:
        return None

    return dt.date(year, month_num, day)

def scrape_bampfa_exhibitions(env='prod', region='sf'):
    """Scrape and process exhibitions from BAMPFA (Berkeley Art Museum and Pacific Film Archive)."""

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
                # Mark if ongoing
                ongoing = True if 'ongoing' in event_dates.lower() else False
                # Handle date ranges
                if '–' in event_dates:
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
                ongoing = None
                
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
                'ongoing': ongoing,
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
                process_event(event_details, region)

    # Scrape current exhibitions
    current_url = 'https://bampfa.org/on-view/exhibitions?field_event_series_type_value=1'
    process_exhibitions(current_url, 'current')

    # Scrape past exhibitions
    past_url = 'https://bampfa.org/on-view/exhibitions/past'
    process_exhibitions(past_url, 'past')