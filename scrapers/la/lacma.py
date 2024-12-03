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

def scrape_lacma_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from LACMA."""
    
    def process_exhibitions(url, phase):
        """Process exhibitions from the given URL for the specified phase."""
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping LACMA {phase} exhibitions --> no soup found")
            return

        exhibitions = soup.find('div', class_='exhibition-list').find_all('div', class_='views-row')

        for exhibition in exhibitions:
            # Extract title
            title_tag = exhibition.find('h2')
            event_title = title_tag.text.strip() if title_tag else None

            # Extract link
            event_link_tag = title_tag.find('a') if title_tag else None
            event_link = 'https://lacma.org' + event_link_tag['href'] if event_link_tag else None

            # Extract date information
            try:
                start_date = exhibition.find('div', class_='views-field-field-start-date').text.strip()
                start_date = start_date.lower().replace(',', '').replace('.', '') if start_date else None
            except:
                try:
                    start_date = exhibition.find('div', class_='views-field-field-alternative-start-date').text.strip()
                    start_date = start_date.lower().replace(',', '').replace('.', '') if start_date else None
                except:
                    start_date = None
            try:
                end_date = exhibition.find('div', class_='views-field-field-end-date').text.strip()
                end_date = end_date.lower().replace(',', '').replace('.', '') if end_date else None
            except:
                try:
                    end_date = exhibition.find('div', class_='views-field-field-alternative-end-date').text.strip()
                    end_date = end_date.lower().replace(',', '').replace('.', '') if end_date else None
                except:
                    end_date = None

            # Check if the exhibition is ongoing
            if end_date:
                if 'ongoing' in end_date:
                    ongoing = True
                    end_date = None
                else:
                    ongoing = False
            else:
                ongoing = False

            # Convert dates if they exist
            if start_date and len(start_date.split()) >= 2:
                start_date = convert_date_to_dt(start_date)
                if start_date:
                    start_date = start_date.strftime("%Y-%m-%d")
                else:
                    start_date = None

            if end_date and len(end_date.split()) >= 2:
                end_date = convert_date_to_dt(end_date)
                if end_date:
                    end_date = end_date.strftime("%Y-%m-%d")
                else:
                    end_date = None

            # Extract description
            description_tag = exhibition.find('div', class_='views-field-field-location-building')
            description_text = description_tag.get_text().strip() if description_tag else None
                        
            # Extract image if available
            img_tag = exhibition.find('img')
            image_link = 'https://lacma.org' + img_tag['src'] if img_tag else None
                        
            event_details = {
                'name': event_title,
                'venue': 'LACMA',
                'description': description_text if description_text else None,
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
    process_exhibitions('https://www.lacma.org/currentexhibitions', 'current')

    # Scrape upcoming exhibitions
    process_exhibitions('https://www.lacma.org/upcomingexhibitions', 'future')

    # Scrape past exhibitions
    process_exhibitions('https://www.lacma.org/pastexhibitions', 'past')
