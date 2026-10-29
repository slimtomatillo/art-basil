from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

HOME_URL = 'https://thegrandgalleryoakland.com/'

# The home page slider mixes shows, classes and events; a show is the slide
# whose text opens with "Show Dates <range>" ("October 2nd – 31st", no year).
_SHOW_DATES_RE = re.compile(r'Show Dates\s+(.+?)\s+(?:Artist|Reception|Opening|$)')
_MAX_DESCRIPTION = 400


def scrape_the_grand_gallery_oakland(env='prod', region='sf'):
    """Scrape and process the shows announced on The Grand Gallery Oakland home page."""

    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("The Grand Gallery Oakland: could not fetch the home page; existing data kept.")
        return

    found = 0
    for slide in soup.select('.et_pb_slide'):
        title_tag = slide.select_one('.et_pb_slide_title')
        content_tag = slide.select_one('.et_pb_slide_content')
        link_tag = slide.select_one('a[href]')
        if not (title_tag and content_tag and link_tag):
            continue
        content = content_tag.get_text(' ', strip=True)
        m = _SHOW_DATES_RE.match(content)
        if not m:
            continue
        name = title_tag.get_text(' ', strip=True)
        start_date, end_date = parse_date_text(m.group(1), today)
        if not (start_date and end_date):
            logging.warning(f"The Grand Gallery Oakland: no readable dates for {name!r}")
            continue
        phase = derive_phase(start_date, end_date, today) or 'current'
        if phase == 'past':
            continue
        description = content[m.end():].strip(' .…')[:_MAX_DESCRIPTION] or None

        event_details = {
            'name': name,
            'venue': 'The Grand Gallery Oakland',
            'description': description,
            'tags': ['exhibition'] + [phase] + ['gallery'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': link_tag['href'], 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        found += 1
        if env == 'dev':
            logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    if not found:
        logging.warning("The Grand Gallery Oakland: no exhibitions found; existing data kept.")
