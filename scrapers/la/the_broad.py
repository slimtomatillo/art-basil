from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import time

def parse_month_day_year(text):
    """Parse 'Month D, YYYY', accepting either an abbreviated ('Oct') or full
    ('October') month name - the site's older and newer templates use different
    ones. Returns a date, or raises ValueError like strptime does."""
    for fmt in ('%b %d, %Y', '%B %d, %Y'):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"time data {text!r} does not match a known month-day-year format")


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

def scrape_exhibition_details(url):
    """Scrape details from an individual exhibition page."""
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning(f"Error scraping exhibition details from {url}")
        return None

    # Get title
    title_tag = soup.find('div', class_='card-header-short__title')
    event_title = title_tag.text.strip() if title_tag else None
    
    # If no title found, try the H1 heading
    if not event_title:
        title_tag = soup.find('h1', class_='heading-hero__title')
        event_title = title_tag.text.strip() if title_tag else None
        if event_title:
            logging.info(f"Found title in heading-hero__title for {url}")

    # The site's newer "nextgen" template (used for at least Featured Installation
    # pages as of 2026-09) has a bare <h1> with no class at all.
    if not event_title:
        title_tag = soup.find('h1')
        event_title = title_tag.get_text(strip=True) if title_tag else None
        if event_title:
            logging.info(f"Found title in a plain h1 (nextgen template) for {url}")

    # Last resort: some pages (e.g. older collection-exhibition pages) have no h1 at
    # all. Without this, a scraped page with no title anywhere ends up stored as the
    # literal string "None" (generate_unique_identifier does f"{name}-{venue}"),
    # colliding with and overwriting whatever the last such page happened to be.
    if not event_title:
        og_title = soup.find('meta', property='og:title')
        event_title = og_title['content'].strip() if og_title and og_title.get('content') else None
        if event_title:
            logging.info(f"Found title in og:title meta tag for {url}")

    # Get dates - try multiple possible classes/locations
    date_text = None
    date_selectors = [
        ('div', 'card-header-short__date'),
        ('div', 'card-header-short__date-line'),
        ('div', 'featured-installation__date'),
        ('div', 'exhibition-date'),
        ('div', 'date-display-single'),
        ('p', 'date'),
        ('div', 'nextgen-dates'),
    ]
    
    for tag, class_name in date_selectors:
        date_tag = soup.find(tag, class_=class_name)
        if date_tag:
            date_text = date_tag.text.strip()
            logging.debug(f"Found date text in {class_name} for {url}")
            break
    
    # If still no date text, look for "Featured Installation" text which implies ongoing
    if not date_text and soup.find(text=lambda t: t and 'Featured Installation' in t):
        date_text = "Featured Installation"
        logging.info(f"Found Featured Installation indicator for {url}")

    # The Infinity Mirror Room is a standing, ticketed installation under /visit/
    # rather than /art/ - unlike a real exhibition page, it has no date text
    # anywhere on the page to detect generically.
    if not date_text and '/visit/mirror-rooms' in url:
        date_text = "Ongoing"

    # Fresh Collection Galleries is a standing free-access rotating display with no
    # date text anywhere on the page either - same situation as the mirror rooms.
    if not date_text and '/art/free-accesss/fresh-collection-galleries' in url:
        date_text = "Ongoing"

    start_date = None
    end_date = None
    ongoing = False
    
    if date_text:
        # Handle various forms of ongoing exhibitions
        normalized_text = date_text.lower().strip()
        ongoing_indicators = ['on view', 'ongoing', 'featured installation', 'permanent']
        
        # First check if it's the "On view [date] through [date]" format
        if 'through' in normalized_text and any(indicator in normalized_text for indicator in ongoing_indicators):
            try:
                # Extract the dates from the format "On view October 11, 2018, through January 20, 2019"
                date_part = normalized_text.split('on view')[-1].strip()
                dates = date_part.split('through')
                start_str = dates[0].strip().strip(',')
                end_str = dates[1].strip()
                
                start_date = dt.datetime.strptime(start_str, '%B %d, %Y').date()
                end_date = dt.datetime.strptime(end_str, '%B %d, %Y').date()
                ongoing = False
            except (ValueError, IndexError) as e:
                logging.warning(f"Could not parse 'On view through' format for {url}: {e}")
        # Then check for other ongoing indicators
        elif any(indicator in normalized_text for indicator in ongoing_indicators):
            ongoing = True
        else:
            # Try to split on various possible separators
            date_parts = None
            for separator in [' - ', '-', '–']:
                if separator in date_text:
                    date_parts = [part.strip() for part in date_text.split(separator)]
                    break
            
            if date_parts and len(date_parts) == 2:
                # Parse start date
                start_parts = date_parts[0].strip().split()
                if len(start_parts) >= 2:  # At least month and day
                    # If year is not in start date, use the year from end date if available
                    if len(start_parts) == 2 and ',' not in date_parts[0]:
                        end_year = date_parts[1].strip().split(',')[-1].strip()
                        start_date_str = f"{date_parts[0].strip()}, {end_year}"
                    else:
                        start_date_str = date_parts[0].strip()
                    try:
                        start_date = parse_month_day_year(start_date_str)
                    except ValueError:
                        logging.warning(f"Could not parse start date '{start_date_str}' for {url}")

                # Parse end date
                if 'ongoing' in date_parts[1].lower():
                    ongoing = True
                else:
                    try:
                        end_date = parse_month_day_year(date_parts[1].strip())
                    except ValueError:
                        logging.warning(f"Could not parse end date '{date_parts[1]}' for {url}")
    else:
        logging.warning(f"No date text found for {url}")

    # Get description - the "nextgen" template (see title fallback above) uses a
    # different class
    description_tag = (soup.find('div', class_='exhibitions-node__body')
                        or soup.find('div', class_='overview-content'))
    description_text = description_tag.get_text().strip() if description_tag else None
    
    # Clean up description text
    if description_text:
        # Replace special characters and clean up whitespace
        description_text = description_text.replace('\xa0', ' ')  # Replace non-breaking space with regular space
        description_text = ' '.join(description_text.split())  # Normalize whitespace and remove extra newlines
        description_text = description_text.strip()

    # Get image
    img_tag = soup.find('img', class_='img-responsive')
    image_link = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None
    if image_link and not image_link.startswith('http'):
        image_link = 'https://www.thebroad.org' + image_link

    return {
        'name': event_title,
        'description': description_text,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': ongoing,
        'image_link': image_link
    }

def scrape_the_broad_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from The Broad."""
    
    def process_exhibitions(url, phase):
        """Process exhibitions from the given URL for the specified phase.
        
        Args:
            url: The URL to scrape
            phase: The phase of exhibitions ('current', 'future', or 'past')
        """
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Error scraping The Broad {phase} exhibitions --> no soup found")
            return

        # Find the container for this phase
        container = None
        if phase == 'future':
            container = soup.find('div', {'id': 'upcoming'})
        elif phase == 'current':
            container = soup.find('div', {'id': 'current'})
        else:
            container = soup.find('div', {'class': 'past-exhibitions'})

        if not container:
            logging.warning(f"Could not find container for {phase} exhibitions")
            return

        # Find all links within the container
        exhibition_links = []
        links = container.find_all('a', {'href': True})
        for link in links:
            href = link['href']
            if not href.startswith('http'):
                href = 'https://www.thebroad.org' + href
            exhibition_links.append(href)
        
        # Process each exhibition
        for event_link in exhibition_links:
            # Add a small delay between requests to be polite
            time.sleep(1)
            
            # Get detailed information from the exhibition page
            details = scrape_exhibition_details(event_link)
            if not details:
                continue
            if not details['name']:
                logging.warning(f"The Broad: no title found by any fallback, skipping {event_link}")
                continue

            event_details = {
                'name': details['name'],
                'venue': 'The Broad',
                'description': details['description'],
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': details['dates'],
                'ongoing': details['ongoing'],
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if details['image_link']:
                event_details['links'].append({'link': details['image_link'], 'description': 'Image'})

            # Add logging for dev environment
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)

    # Scrape current exhibitions from the main page
    process_exhibitions('https://www.thebroad.org/art', 'current')

    # Scrape upcoming exhibitions from the main page
    process_exhibitions('https://www.thebroad.org/art', 'future')

    # Scrape past exhibitions from their dedicated page
    process_exhibitions('https://www.thebroad.org/art/exhibitions/past', 'past') 