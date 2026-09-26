from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://lacma.org'
MAX_DESCRIPTION_CHARS = 500
_DATE_FORMATS = ('%B %d, %Y', '%b %d, %Y')


def parse_one_date(text):
    text = ' '.join(text.replace('\xa0', ' ').split())
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_card_dates(text):
    """Parse the grid layout's date line, e.g. 'June 14, 2026–October 12, 2026'.
    Returns (start_date, end_date, ongoing)."""
    text = ' '.join((text or '').replace('\xa0', ' ').split())
    ongoing = 'ongoing' in text.lower()
    parts = [part.strip() for part in re.split(r'\s*[–—-]\s*', text)]
    end_date = None if ongoing or len(parts) < 2 else parse_one_date(parts[-1])
    start_date = parse_one_date(parts[0])
    if start_date is None and end_date is not None:
        # "June 14–October 12, 2026": the start omits the year
        start_date = parse_one_date(f"{parts[0]}, {end_date.year}")
    return start_date, end_date, ongoing


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

        def emit(event_title, event_link, start_date, end_date, ongoing, description_text, image_link):
            event_details = {
                'name': event_title,
                'venue': 'LACMA',
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

            # Add logging for dev environment
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)

        # Layout introduced in Sept 2026 (current/past pages): article.exhibition cards
        grid_cards = soup.select('article.exhibition')
        if grid_cards:
            for card in grid_cards:
                try:
                    title_tag = card.find('h3')
                    if not title_tag or not title_tag.get_text(strip=True):
                        continue
                    link_tag = card.find('a', href=True)
                    href = link_tag['href'] if link_tag else None
                    event_link = (href if href.startswith('http') else BASE_URL + href) if href else None

                    date_tag = card.select_one('header p')
                    start_date, end_date, ongoing = parse_card_dates(date_tag.get_text(strip=True) if date_tag else None)
                    if not start_date and not end_date and not ongoing:
                        logging.warning(f"LACMA: could not parse dates for {title_tag.get_text(strip=True)!r}")

                    description_tag = card.select_one('.event-list-view .rich-text')
                    description_text = ' '.join(description_tag.get_text(' ', strip=True).split()) if description_tag else None
                    if description_text and len(description_text) > MAX_DESCRIPTION_CHARS:
                        description_text = description_text[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'

                    img_tag = card.find('img')
                    image_link = None
                    if img_tag and img_tag.get('src'):
                        src = img_tag['src']
                        image_link = src if src.startswith('http') else BASE_URL + src

                    emit(' '.join(title_tag.get_text(' ', strip=True).split()), event_link,
                         start_date, end_date, ongoing, description_text or None, image_link)
                except Exception:
                    logging.exception(f"LACMA: failed to process a {phase} exhibition card")
            return

        # Legacy layout (still used by the upcoming page)
        exhibition_list = soup.find('div', class_='exhibition-list')
        if exhibition_list is None:
            logging.warning(f"Error scraping LACMA {phase} exhibitions --> exhibition markup not recognised")
            return
        exhibitions = exhibition_list.find_all('div', class_='views-row')

        for exhibition in exhibitions:
            # Extract title
            title_tag = exhibition.find('h2')
            event_title = title_tag.text.strip() if title_tag else None

            # Extract link
            event_link_tag = title_tag.find('a') if title_tag else None
            event_link = None
            if event_link_tag and event_link_tag.get('href'):
                href = event_link_tag['href']
                event_link = href if href.startswith('http') else 'https://lacma.org' + href

            # Extract date information
            try:
                start_date = exhibition.find('div', class_='views-field-field-start-date').text.strip()
                start_date = start_date.lower().replace(',', '').replace('.', '')
            except:
                try:
                    start_date = exhibition.find('div', class_='views-field-field-alternative-start-date').text.strip()
                    start_date = start_date.lower().replace(',', '').replace('.', '')
                except:
                    start_date = None
            try:
                end_date = exhibition.find('div', class_='views-field-field-end-date').text.strip()
                end_date = end_date.lower().replace(',', '').replace('.', '')
            except:
                try:
                    end_date = exhibition.find('div', class_='views-field-field-alternative-end-date').text.strip()
                    end_date = end_date.lower().replace(',', '').replace('.', '')
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

            if start_date and end_date:                
                # Handle cases with complete start and end dates
                if len(start_date.split()) == 3 and len(end_date.split()) == 3:
                    start_date = convert_date_to_dt(start_date)
                    end_date = convert_date_to_dt(end_date)
                # Handle cases where the start date is missing the year but the end date has it
                elif len(start_date.split()) == 2 and len(end_date.split()) == 3:
                    start_date = convert_date_to_dt(start_date + ' ' + end_date.split()[-1])  # Append year from end date
                    end_date = convert_date_to_dt(end_date)
                # Handle cases where the start and end dates share the same year
                elif len(start_date.split()) == 2 and len(end_date.split()) == 2:
                    shared_year = dt.datetime.now().year  # Default to the current year if not specified
                    start_date = convert_date_to_dt(start_date + ' ' + str(shared_year))
                    end_date = convert_date_to_dt(end_date + ' ' + str(shared_year))
            elif start_date:
                start_date = convert_date_to_dt(start_date)
                        
            # Extract description
            description_tag = exhibition.find('div', class_='views-field-field-location-building')
            description_text = description_tag.get_text().strip() if description_tag else None

            # Extract image if available. LACMA serves some images from an
            # absolute host (www-images.lacma.org) and others as site-relative
            # paths, so only prepend the base URL when it's relative.
            img_tag = exhibition.find('img')
            image_link = None
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                image_link = src if src.startswith('http') else 'https://lacma.org' + src
                        
            emit(event_title, event_link, start_date, end_date, ongoing, description_text, image_link)

    # Scrape current exhibitions
    process_exhibitions('https://www.lacma.org/currentexhibitions', 'current')

    # Scrape upcoming exhibitions
    process_exhibitions('https://www.lacma.org/upcomingexhibitions', 'future')

    # Scrape past exhibitions
    process_exhibitions('https://www.lacma.org/pastexhibitions', 'past')
