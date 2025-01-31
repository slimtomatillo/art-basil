from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def scrape_asian_art_museum_current_events(env='prod', region='sf'):
    """Scrape and process current events from Asian Art Museum."""

    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""

        date_parts = date_string.split()
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1])
        if len(date_parts) == 3:
            year = int(date_parts[2])
        else:
            year = dt.datetime.now().year
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

    # Scrape info
    url = 'https://exhibitions.asianart.org/'
    soup = fetch_and_parse(url)
    
    # Get featured event (formatted differently than other events)
    featured_event = soup.find(class_='hero-card -wrap')

    # Check if featured event was found
    if featured_event:

        # Extract title and title-link
        title_tag = featured_event.find(class_='hero-card__title')
        if title_tag:
            event_title = title_tag.text.strip()
            event_link = title_tag.get('href')
        else:
            event_title, event_link = None, None

        # Extract image link if possible
        try:
            image_link = featured_event.find(class_='hero-card__image-src')['src']
        except TypeError:
            image_link = None

        # Extract date info
        date_element = featured_event.find(class_='hero-card__aside')
        event_date = date_element.find('span').text.lower().replace(',', '').strip()
        ongoing = True if event_date == 'ongoing' else False
        phase = 'current'
        if 'open' in date_element.text.lower(): # This implies the date corresponds to the opening date
            start_date = convert_date_to_dt(event_date)
            end_date = None # Ideally scrape the exhibition page to get the end date
            if start_date > dt.datetime.now().date():
                phase = 'future'
        else: # This implies the date correspond to the closing date
            start_date = None
            if event_date:
                event_date = event_date.replace('through ', '')
                end_date = convert_date_to_dt(event_date)
            else:
                end_date = None

        # Extract description
        description_tag = featured_event.find('div', class_='hero-card__desc')
        # Extracting all text within the div
        if description_tag:
            extracted_text = description_tag.get_text(separator=' ', strip=True)
            # Additional string manipulation to correct spacing issues before 's'
            corrected_text = extracted_text.replace(' s ', 's ')
            event_description = corrected_text
        else:
            event_description = None

        event_details = {
            'name': event_title,
            'venue': 'Asian Art Museum',
            'description': event_description,
            'tags': ['exhibition'] + [phase] + ['museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing,
            'links': [
                {
                    'link': event_link,
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

        # Add logging for dev environment
        if env == 'dev':
            logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")

        if env == 'prod':
            process_event(event_details, region)

    # Find rest of events
    events_list = soup.find_all(class_='card split-grid__card split-grid__card--dark')

    # Check if events were found
    if events_list:

        for event in events_list:
            # Extract title and title link
            title_tag = event.find(class_='card__title')
            if title_tag:
                event_title = title_tag.text.strip()
                event_link = title_tag['href']
            else:
                event_title, event_link = None, None

            # Extract image link if possible
            try:
                image_link = event.find(class_='card__img').find('a').find('img')['src']
            except AttributeError:
                image_link = None

            # Extract date label
            event_date = event.find('div', class_='card__subtitle').text.strip().lower().replace(',', '').replace('through ', '')
            ongoing = True if event_date.strip() in ['ongoing', 'now on view'] else False
            start_date = None
            if event_date in ['ongoing', 'now on view']:
                end_date = None
            # Special case for January 2025
            elif event_date == 'january 2025':
                end_date = convert_date_to_dt('january 31 2025')
            # Handle "opens"
            elif 'opens' in event_date:
                start_date = convert_date_to_dt(event_date.split('opens')[1].strip())
                end_date = None
            elif event_date:
                end_date = convert_date_to_dt(event_date)
            else:
                end_date = None

            # Extract description
            description_tag = event.find('div', class_='card__body')
            event_description = description_tag.get_text(separator='\n').strip() if description_tag else None

            # Identify phase
            phase = 'current'

            event_details = {
                'name': event_title,
                'venue': 'Asian Art Museum',
                'description': event_description,
                'tags': ['exhibition'] + [phase] + ['museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [
                    {
                        'link': event_link,
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

            # Add logging for dev environment
            if env == 'dev':
                logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")

            if env == 'prod':
                process_event(event_details, region)

def scrape_asian_art_museum_past_events(env='prod', region='sf'):
    """Scrape and process past events from Asian Art Museum."""
    
    def convert_date_to_dt(date_string):
        """Takes a date in string form and converts it to a dt object"""

        date_parts = date_string.split()
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1])
        if len(date_parts) == 3:
            year = int(date_parts[2])
        else:
            year = dt.datetime.now().year
        if month_num and day and year:
            date_dt = dt.date(year, month_num, day)
        return date_dt

    # Scrape info
    url = 'https://exhibitions.asianart.org/past/'
    soup = fetch_and_parse(url)
    
    # Find rest of events
    article_elements = soup.find(class_='exhibit-archive').find(class_='exhibit__content').find_all('article')
    articles = []
    for e in article_elements:
        a = e.find_all('article')
        # Check if there are articles in the element
        if len(a) > 0:
            # Check if the element is not an empty year card
            if 'no results for this year' not in e.text.lower():
                # Check if the element is not a year card
                if 'card-slash' not in e['class']:
                    articles += a

    # Check if events were found
    if articles:

        for article in articles:

            # Extract title and title link
            title_tag = article.find('a', class_='card__title')
            if title_tag:
                event_title = title_tag.text.strip()
                event_link = title_tag['href']
            else:
                event_title, event_link = None, None

            # Extract image link if possible
            img_tag = article.find('img', class_='card__img-src')
            if img_tag:
                image_link = img_tag['src']
            else:
                image_link = None

            # Extract date information
            date_tag = article.find('div', class_='card__subtitle')
            event_dates = date_tag.text.strip() if date_tag else None
            dates = event_dates.lower().replace(',', '').split('–')
            if event_dates:
                start_date = convert_date_to_dt(dates[0])
                end_date = convert_date_to_dt(dates[1])
            else:
                start_date = None
                end_date = None

            # Identify phase
            phase = 'past'

            event_details = {
                'name': event_title,
                'venue': 'Asian Art Museum',
                'description': None,
                'tags': ['exhibition'] + [phase] + ['museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'links': [
                    {
                        'link': event_link,
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

            # Add logging for dev environment
            if env == 'dev':
                logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")

            if env == 'prod':
                process_event(event_details, region)