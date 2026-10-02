from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://www.moadsf.org'
EXHIBITIONS_URL = BASE_URL + '/exhibitions'

# The Past tab is a paginated archive going back years (4 shows per page);
# only the most recent pages are worth re-scraping daily.
MAX_PAST_PAGES = 3

# MoAD's site is Webflow: Current, Upcoming and Past are tab panes on the same
# page, keyed by these ids.
TAB_PHASES = {'current': 'current', 'upcoming': 'future', 'past': 'past'}

def convert_date_to_dt(date_string):
    """Takes a date in string form (e.g. 'Sep 30, 2026' or 'August 16, 2026') and converts it to a dt object"""

    date_parts = date_string.lower().replace(',', '').split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    day = int(date_parts[1])
    year = int(date_parts[2])
    return dt.date(year, month_num, day)

def field_text(item, field):
    tag = item.find(attrs={'fs-cmsfilter-field': field})
    return tag.get_text(strip=True) if tag else None

def extract_dates(item):
    """Each item lists its dates twice: long form ('Sep 30, 2026 - May 30, 2027')
    and short form ('9.30.26 - 5.30.27'). Only the long form is reliable - on past
    shows the short end date just repeats the start date."""
    row = item.find(class_='current-exhibition_text-row')
    if not row:
        return None, None
    long_dates = [div.get_text(strip=True) for div in row.find_all('div', recursive=False)
                  if any(ch.isalpha() for ch in div.get_text(strip=True))]
    dates = []
    for date_text in long_dates[:2]:
        try:
            dates.append(convert_date_to_dt(date_text))
        except (KeyError, ValueError, IndexError):
            logging.warning(f"MoAD: could not parse date {date_text!r}")
            dates.append(None)
    while len(dates) < 2:
        dates.append(None)
    return dates[0], dates[1]

def extract_title(item):
    """The 'name' field is usually the show title, but some shows put the main
    title in the 'artist' slot in capitals (e.g. 'UNBOUND' / 'Art, Blackness &
    the Universe'), so join those back together."""
    name = field_text(item, 'name')
    artist = field_text(item, 'artist')
    if artist and name and artist.isupper() and len(artist) > 1:
        return f"{artist}: {name}"
    return name or artist

def scrape_description(event_url):
    soup = fetch_and_parse(event_url)
    if soup is None:
        return None
    meta = soup.find('meta', attrs={'name': 'description'})
    description = meta.get('content', '') if meta else ''
    if not description.strip():
        # Some shows leave the SEO description empty - fall back to the opening
        # paragraph of the body text (later ones drift into artist bios).
        body = soup.find(class_='text-rich-text')
        paragraphs = [p.get_text(' ', strip=True).replace('‍', '') for p in body.find_all('p')] if body else []
        description = next((p for p in paragraphs if p.strip()), '')
    return ' '.join(description.split()) or None

def scrape_moad_exhibitions(env='prod', region='sf'):
    """Scrape and process exhibitions from the Museum of the African Diaspora."""

    today = region_today(region)
    seen_links = set()
    url = EXHIBITIONS_URL
    past_pages = 0

    while url:
        soup = fetch_and_parse(url)
        if soup is None:
            return
        past_pages += 1
        next_url = None

        for tab_id, tab_phase in TAB_PHASES.items():
            pane = soup.find(class_='w-tab-pane', id=tab_id)
            if not pane:
                logging.warning(f"MoAD: '{tab_id}' tab not found on {url}")
                continue

            # Paginating the archive re-renders the whole page, so the Current
            # and Upcoming tabs repeat on every page - skip shows already seen.
            for item in pane.find_all(class_='exhibition-list_item'):
                link_tag = item.find('a', href=True)
                if not link_tag:
                    continue
                event_link = BASE_URL + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
                if event_link in seen_links:
                    continue
                seen_links.add(event_link)

                event_title = extract_title(item)
                start_date, end_date = extract_dates(item)
                # MoAD is slow to move shows between tabs (a show can still sit
                # under Upcoming after it opens), so trust the dates over the tab.
                phase = derive_phase(start_date, end_date, today) or tab_phase

                image_tag = item.find('img', class_='exhibition-list_image')
                image_link = image_tag.get('src') if image_tag else None

                event_details = {
                    'name': event_title,
                    'venue': 'Museum of the African Diaspora',
                    'description': scrape_description(event_link),
                    'tags': ['exhibition'] + [phase] + ['museum'],
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

                # Add dev environment logging
                if env == 'dev':
                    logging.info(f"Event found: {event_details['name']} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")

                # Process event in prod environment
                if env == 'prod':
                    process_event(event_details, region)

            if tab_id == 'past':
                next_tag = pane.find('a', class_='w-pagination-next', href=True)
                if next_tag and past_pages < MAX_PAST_PAGES:
                    next_url = EXHIBITIONS_URL + next_tag['href']

        url = next_url
