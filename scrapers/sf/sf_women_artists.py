from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

# Longest names first so e.g. "june" matches before the "jun" abbreviation
# would otherwise eat only part of it.
_MONTH_PATTERN = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# A date range, e.g. "July 4 – August 5th", "Oct. 3 – Nov. 4", or
# "June 3 – 27, 2025". Matched with .search() rather than against the whole
# line, since the surrounding prose (an exhibition title, "An SFWA Members'
# Exhibition,") is free-form and shouldn't have to be stripped out first.
_DATE_RANGE_RE = re.compile(
    rf'\b(?P<start>(?:{_MONTH_PATTERN})\.?\s*\d{{1,2}}(?:st|nd|rd|th)?)'
    rf'\s*(?:–|—|-|to)\s*'
    rf'(?P<end>(?:(?:{_MONTH_PATTERN})\.?\s*)?\d{{1,2}}(?:st|nd|rd|th)?)'
    rf'(?:,?\s*(?P<year>\d{{4}}))?',
    re.IGNORECASE,
)

def scrape_event_specific_page(event_url):
    """Given the url for a specific event, scrape info"""

    # Scrape info and collect events
    soup = fetch_and_parse(event_url)
    if soup is None:
        logging.warning(f"Could not fetch event page: {event_url}")
        return None, None, None

    header = soup.find('header', class_='article-header')
    if not header:
        return None, None, None

    # The site mixes a <p>-based layout with a <ul><li><strong> one, and some
    # pages have both (e.g. an image-only <p> alongside the real <li> text) -
    # gather both tag types, in document order, rather than picking just one.
    text_blocks = header.find_all(['p', 'li'])

    # Get date info. Each block can bundle several logical lines separated by
    # <br> (e.g. "An SFWA Members' Exhibition,<br>May 8th – June 2nd<br>..."),
    # and some pages instead put the title and dates on one single line (e.g.
    # "Open Call Exhibition, July 4 – August 5th"). Rather than requiring the
    # whole line to be date-only text, search each line for just the date
    # range substring - that way free-form prose ("An SFWA Members'
    # Exhibition,", "Open Call Exhibition,") around it doesn't matter, and the
    # opening-reception line is naturally skipped since "5:30 – 8pm" has no
    # month name for the pattern to match.
    event_dates = None
    for block in text_blocks:
        lines = block.get_text('\n').split('\n')
        for line in lines:
            # Normalize non-breaking spaces (seen as "June&nbsp;6 – July&nbsp;1")
            # to regular spaces so later whitespace-based splitting works.
            text = line.strip().lower().replace('\xa0', ' ')
            if not text or 'reception' in text:
                continue
            match = _DATE_RANGE_RE.search(text)
            if match:
                event_dates = f"{match['start']} – {match['end']}"
                if match['year']:
                    event_dates += f" {match['year']}"
                event_dates = event_dates.replace('th', '').replace('rd', '').replace('nd', '').replace('1st', '1').replace(',', '').replace('.', '')
                break
        if event_dates:
            break

    # Get event description - the first block with actual text (skips e.g.
    # an image-only <p> that carries no text of its own).
    event_description = next(
        (text for block in text_blocks if (text := block.get_text(' ', strip=True))),
        None,
    )

    # Get image link
    img_container = soup.find('div', class_='ngg-gallery-thumbnail')
    image_link = None
    if img_container:
        first_link_tag = img_container.find('a')
        if first_link_tag:
            image_link = first_link_tag.get('href')

    return event_dates, event_description, image_link

def convert_date_to_nums(date_string):
    """Takes a date in string form and converts it to ints"""
    try:
        date_parts = date_string.strip().split()
        if not date_parts:
            return None, None
        month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
        day = int(date_parts[1])
        return month_num, day
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"Error converting date string '{date_string}': {str(e)}")
        return None, None

def scrape_sfwomenartists(env='prod', region='sf'):
    """Scrape and process events from San Francisco Women Artists Gallery."""
    
    # Declare url
    url = 'https://www.sfwomenartists.org/exhibitions/'
    
    # Scrape info and collect events
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning("Error scraping San Francisco Women Artists Gallery --> no soup found")
        return

    # Find all events
    events_list = soup.find_all(class_='exhibition-item')

    # Check if events is found
    if events_list:
        for event in events_list:
            # Extract title and title-link
            title_tag = event.find('h4', class_='gallery-title')
            link_tag = event.find('a')
            if not title_tag or not link_tag:
                logging.warning("Skipping exhibition-item with missing title or link")
                continue
            event_title = title_tag.text.strip()
            event_link = link_tag['href'].strip()

            # Scrape additional info from event url
            event_dates, event_description, image_link = scrape_event_specific_page(event_link)
            # Skip to the next event if end date does not exist
            if not event_dates:
                # The gallery's archive back to 2017 has shows whose pages never
                # gave a date range (only "Until July 31, 2020", a reception, or
                # nothing). Those are expected and permanent, so keep the warning
                # for recent shows, where a missing date means the page layout
                # has changed again.
                try:
                    listing_year = int(event.find('p').text.split(' ')[-1])
                except (AttributeError, ValueError, IndexError):
                    listing_year = None
                if listing_year is not None and listing_year <= dt.date.today().year - 2:
                    logging.info(f"No date range for archived event: {event_title} ({listing_year}) at {event_link}")
                else:
                    logging.warning(f"No valid dates found for event: {event_title} at {event_link}")
                continue
            
            # Handle edge cases
            if event_dates == 'august 10 2020':
                event_dates = 'august 10 2020 – august 31 2020'
            elif event_dates == 'september 1 – 25 2020':
                event_dates = 'september 1 2020 – september 25 2020'
            elif event_dates == 'october 2024 exhibition':
                event_dates = 'october 8 2024 – november 1 2024'
            elif event_dates == 'november 5 – 30 2019':
                event_dates = 'november 5 2019 – november 30 2019'

            # Extract date information
            dates = [d.strip() for d in event_dates.split('–')]
            start_date_month, start_date_day = convert_date_to_nums(dates[0])
            if start_date_month is None or start_date_day is None:
                logging.warning(f"Could not parse start date from '{dates[0]}' for event: {event_title}")
                continue
                            
            # If no end month, use the start month
            end_tokens = dates[1].split(' ')
            if len(end_tokens) == 1:
                end_date_month = start_date_month
                end_date_day = int(dates[1])
            elif len(end_tokens) == 2 and all(t.isdigit() for t in end_tokens):
                # Same-month range with a trailing year attached to the end day,
                # e.g. "june 3 – 27 2025" (also covers what "august 3 – 27 2021"
                # and "june 1 – 25 2021" were previously hardcoded for).
                end_date_month = start_date_month
                end_date_day = int(end_tokens[0])
            else:
                end_date_month, end_date_day = convert_date_to_nums(dates[1])
                if end_date_month is None or end_date_day is None:
                    logging.warning(f"Could not parse end date from '{dates[1]}' for event: {event_title}")
                    continue

            year_tag = event.find('p')
            try:
                year = int(year_tag.text.split(' ')[-1])
            except (AttributeError, ValueError, IndexError):
                logging.warning(f"Could not parse year for event: {event_title}")
                continue
            
            if start_date_month and start_date_day and year:
                start_date = dt.date(year, start_date_month, start_date_day)
            else:
                start_date = None
            
            if end_date_month and end_date_day and year:
                # If the end date is in the next year, set it to the next year
                if start_date_month == 12 and end_date_month == 1:
                    year += 1
                end_date = dt.date(year, end_date_month, end_date_day)
            else:
                end_date = None
                
            # Identify phase
            today = dt.datetime.today().date()
            if (start_date != None) and (end_date != None):
                if (start_date <= today) and (end_date >= today):
                    phase = 'current'
                elif (start_date > today) and (end_date > today):
                    phase = 'future'
                elif (start_date < today) and (end_date < today):
                    phase = 'past'
            else:
                phase = None

            event_details = {
                'name': event_title,
                'venue': 'San Francisco Women Artists Gallery',
                'description': event_description,
                'tags': ['exhibition'] + [phase] + ['gallery'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
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
            
            # Add debug logging for dev environment
            if env == 'dev':
                logging.info(f"Event found: {event_details.get('name')} at {event_details.get('venue')}")
            
            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)

    else:
        logging.warning(f"Events not found for San Francisco Women Artists Gallery")