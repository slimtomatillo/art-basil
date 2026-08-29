from utils import fetch_and_parse
from processing import process_event
import calendar
import datetime as dt
from datetime import timezone
import logging
import re

LISTING_URL = 'https://phi.ca/en/whats-on/'
# phi.ca serves stripped HTML (no exhibition cards) to the default bot
# User-Agent from datacenter IPs; a browser UA gets the full page.
BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
_MONTHS['sept'] = 9

# "Exhibition • Contemporary Art Apr. 23 → Sep. 13 Jakob Kudsk Steensen: Otherworlds 451 Saint-Jean Street"
_DATE_RANGE_RE = re.compile(
    r'([A-Za-z]+)\.?\s+(\d{1,2})\s*(?:→|–|-|to)\s*([A-Za-z]+)\.?\s+(\d{1,2})')
_TRAILING_ADDRESS_RE = re.compile(r'\s*\d+\s+\S.*?\bStreet\s*$')


def month_num(name):
    return _MONTHS.get(name.strip('. ').lower())


def infer_dates(start_month, start_day, end_month, end_day, today):
    """The listing carries no year. Everything on 'What's On' is current or
    upcoming, so anchor the start to the current year and roll the end over if
    it wraps past December."""
    if not (start_month and end_month):
        return None, None
    start_year = today.year
    end_year = start_year if end_month >= start_month else start_year + 1
    try:
        return dt.date(start_year, start_month, start_day), dt.date(end_year, end_month, end_day)
    except ValueError:
        return None, None


def scrape_phi_foundation_exhibitions(env='prod', region='mtl'):
    """Scrape and process exhibitions from the PHI Foundation for Contemporary Art."""

    soup = fetch_and_parse(LISTING_URL, headers=BROWSER_HEADERS)
    if soup is None:
        logging.warning("Error scraping PHI Foundation exhibitions --> no soup found")
        return

    articles = soup.find_all('article', class_='leading-10')
    if not articles:
        logging.warning("PHI Foundation: no article cards found")
        return

    today = dt.datetime.now().date()

    for article in articles:
        text = ' '.join(article.get_text(' ', strip=True).split())
        # Only the exhibitions (skip "Event", "Experience", ...)
        if not text.lower().startswith('exhibition'):
            continue

        link_tag = next((a for a in article.find_all('a', href=True)
                         if '/en/events/' in a['href']), None)
        if not link_tag:
            continue
        event_link = link_tag['href']

        date_match = _DATE_RANGE_RE.search(text)
        start_date = end_date = None
        if date_match:
            start_date, end_date = infer_dates(
                month_num(date_match.group(1)), int(date_match.group(2)),
                month_num(date_match.group(3)), int(date_match.group(4)), today)

        # Title = what's left after the type/category prefix, the date range,
        # and the trailing venue address.
        title_part = text
        if date_match:
            title_part = text[date_match.end():]
        title_part = _TRAILING_ADDRESS_RE.sub('', title_part).strip()
        event_title = title_part or link_tag.get_text(' ', strip=True)
        if not event_title:
            continue

        if end_date and end_date < today:
            phase = 'past'
        elif start_date and start_date > today:
            phase = 'future'
        else:
            phase = 'current'

        img_tag = article.find('img')
        image_link = None
        if img_tag:
            image_link = img_tag.get('src') or img_tag.get('data-src')

        event_details = {
            'name': event_title,
            'venue': 'PHI Foundation',
            'description': None,
            'tags': ['exhibition', phase, 'gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': event_link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        # Add logging for dev environment
        logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        # Process event in prod environment
        if env == 'prod':
            process_event(event_details, region)
