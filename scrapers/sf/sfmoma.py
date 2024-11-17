from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
from unicodedata import normalize
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

def scrape_sfmoma(env='prod', region='sf'):
    """Scrape and process events from SFMOMA."""
    
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
                    process_event(event_details, region)

            except Exception as e:
                logging.error(f"Error processing event: {e}", exc_info=True)
