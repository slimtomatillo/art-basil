from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://soex.org'
CURRENT_UPCOMING_URL = BASE_URL + '/projects-exhibitions/current-upcoming'

# The "Past" page is a mixed archive back to 1999 (exhibitions, one-off events
# and projects together), so only Current + Upcoming is scraped; shows age
# into 'past' on their own once their end date passes.

def iso_date(tag):
    """The <span> date tags carry an ISO timestamp (with time zone) in `content`."""
    if tag is None or not tag.get('content'):
        return None
    return dt.date.fromisoformat(tag['content'][:10])

def extract_dates(event_url):
    """Cards only show a single date; the show's own page has the full range."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None, None
    start = iso_date(soup.select_one('.date-display-start'))
    end = iso_date(soup.select_one('.date-display-end'))
    if not start:
        start = iso_date(soup.select_one('.date-display-single'))
    return start, end

def scrape_southern_exposure(env='prod', region='sf'):
    """Scrape and process current and upcoming exhibitions from Southern Exposure."""

    today = region_today(region)
    soup = fetch_and_parse(CURRENT_UPCOMING_URL)
    if soup is None:
        logging.warning("Southern Exposure: could not fetch the current/upcoming page; existing data kept.")
        return

    for row in soup.select('.view-content .views-row'):
        link_tag = row.find('a', class_='blockLink', href=True)
        title_tag = row.find('h2')
        if not link_tag or not title_tag:
            continue

        name = title_tag.get_text(' ', strip=True)
        event_link = BASE_URL + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']

        start_date, end_date = extract_dates(event_link)
        if not (start_date or end_date):
            # Fall back to the card's own single date (an opening day)
            start_date = iso_date(row.select_one('.date-display-single'))
        if not (start_date or end_date):
            logging.warning(f"Southern Exposure: no readable dates for {name!r}")
            continue

        phase = derive_phase(start_date, end_date, today) or 'current'

        image_tag = row.find('img', src=True)
        image_link = image_tag['src'] if image_tag else None

        blurb = row.select_one('.link-body')
        subtitle = row.select_one('.subtitle')
        description = (blurb or subtitle).get_text(' ', strip=True) if (blurb or subtitle) else None

        event_details = {
            'name': name,
            'venue': 'Southern Exposure',
            'description': description or None,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
