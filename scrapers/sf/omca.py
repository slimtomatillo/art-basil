from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_text):
    """Convert date text to a datetime object, determining the year based on the next occurrence."""

    # Get current date
    today = dt.date.today()
    current_year = today.year

    # Split the date text
    date_parts = date_text.lower().strip().split()
    month_str = date_parts[0]
    day = int(date_parts[1])

    # Convert month to number
    month = MONTH_TO_NUM_DICT[month_str]

    # Determine if the year is provided
    if len(date_parts) == 3:
        year = int(date_parts[2])
    else:
        # Determine the year based on the next occurrence of the date
        if month < today.month or (month == today.month and day < today.day):
            year = current_year + 1
        else:
            year = current_year

    # Create the date object
    return dt.date(year, month, day)

def scrape_oak_museum_of_ca_exhibitions(env='prod', region='sf'):
    """Scrape and process events from the Oakland Museum of California (OMCA)."""
    
    def fetch_event_details(event_url):
        """Fetch and parse details from the event's page."""
        
        event_soup = fetch_and_parse(event_url)
        if not event_soup:
            return None, None, None

        # Find all header tags (h1, h2, h3, h4, h5, h6)
        header_tags = event_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for header in header_tags:
            date_text = header.get_text(strip=True).lower().replace('-', '–') # make dashes the same
            # Handle edge cases
            if '“' in date_text:
                continue

            if any(keyword in date_text for keyword in ['now on view', 'on view now', 'opens', 'on view through', 'ongoing', '–']):
                # Check for certain header tags to skip
                if date_text.strip() == 'angela davis–seize the time':
                    continue
                # Exhibition is on view
                elif 'now on view' in date_text:
                    return None, None, True
                # On view now
                elif 'on view now' in date_text:
                    # Handle 'Calli: The Art of Xicanx Peoples'
                    if event_url == 'https://museumca.org/on-view/calli-the-art-of-xicanx-peoples/':
                        return convert_date_to_dt('june 14 2024'), convert_date_to_dt('january 26 2025'), False
                    else:
                        return None, None, True
                # Ongoing exhibition
                elif 'on view through' in date_text:
                    return None, None, True
                # Ongoing exhibition
                elif 'ongoing' in date_text:
                    return None, None, True
                # Opening in the future
                elif 'opens' in date_text:
                    date_text = date_text.replace('opens ', '').split(' | ')
                    start_date = convert_date_to_dt(date_text[0])
                    return start_date, None, False
                # Past exhibition
                elif '–' in date_text:
                    date_text = date_text.replace(',', '').replace('.', '').split(' | ')[0].split(' i ')[0].split('–')
                    start_date = convert_date_to_dt(date_text[0])
                    end_date = convert_date_to_dt(date_text[1]) if len(date_text) > 1 else None
                    ongoing = False
                    return start_date, end_date, ongoing

        # Otherwise, it's a past exhibition
        date_text = event_soup.find('h1', class_='wp-block-post-title').find_next('p')
        if date_text:
            date_text = date_text.get_text(strip=True).lower().replace(',', '').split('–')
            start_date = convert_date_to_dt(date_text[0])
            end_date = convert_date_to_dt(date_text[1]) if len(date_text) > 1 else None
            ongoing = False
            return start_date, end_date, ongoing

        return None, None, False

    url = 'https://museumca.org/on-view/#exhibitions'
    soup = fetch_and_parse(url)
    if soup is None:
        logging.info('Error scraping OMCA exhibitions')
        return

    exhibition_elements = soup.find_all('div', class_='post-tile post-tile_type-on-view')

    for elem in exhibition_elements:
        try:
            # Extract title
            title = elem.find('span', class_='post-tile__title').text.strip()

            # Extract description
            description = elem.find('span', class_='post-tile__excerpt').text.strip().replace('\n', '').replace('\xa0', ' ')

            # Extract location
            location_tag = elem.find('span', class_='post-tile__tax-location')
            location = location_tag.text.strip() if location_tag else None

            # Extract event link
            event_link_tag = elem.find('a', class_='post-tile__inner', href=True)
            event_link = event_link_tag['href'] if event_link_tag else None
            
            # Extract dates
            start_date, end_date, ongoing = fetch_event_details(event_link)

            # Extract image link
            image_tag = elem.find('img', src=True)
            image_link = image_tag['src'] if image_tag else None

            # Identify phase
            today = dt.datetime.today().date()
            if start_date != None and end_date != None:
                if start_date <= today <= end_date:
                    phase = 'current'
                elif today < start_date:
                    phase = 'future'
                else:
                    phase = 'past'
            elif ongoing == True:
                phase = 'current'
            else:
                phase = None

            event_details = {
                'name': title,
                'venue': 'Oakland Museum of California',
                'description': description,
                'tags': ['exhibition', phase, 'museum'] if phase else ['exhibition', 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Add image link if it exists
            if image_link:
                event_details['links'].append({'link': image_link, 'description': 'Image'})

            if env == 'prod':
                process_event(event_details, region)

        except Exception as e:
            logging.warning(f"Error parsing element of url {event_link}: {e}")
            continue