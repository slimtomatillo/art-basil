from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re

BASE_URL = 'https://www.waltdisney.org'

_DATE_LINE_RE = re.compile(r'\d{4}')

def convert_date_to_dt(date_string):
    """Takes a date in string form (e.g. 'oct 23 2026' or 'october 2025' for a
    rotating series with no specific day) and converts it to a dt object"""

    date_parts = date_string.split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    if len(date_parts) == 2 and int(date_parts[1]) > 31:
        # "month year" only - no day given, default to the 1st
        day = 1
        year = int(date_parts[1])
    else:
        day = int(date_parts[1])
        year = int(date_parts[2])
    if month_num and day and year:
        date_dt = dt.date(year, month_num, day)
    return date_dt

def extract_date_text(date_div):
    """The date field can bundle an unrelated line (a subtitle, hours) with the
    actual date range via <br>, in either order - pick whichever line has a
    4-digit year rather than assuming position. Returns None when no line
    looks like a date at all (e.g. a virtual exhibit just labeled "Open Now")."""
    lines = date_div.get_text('\n', strip=True).split('\n')
    for line in lines:
        if _DATE_LINE_RE.search(line):
            return line
    return None

def parse_date_range(date_text, today):
    """Returns (phase, start_date, end_date) for a 'Mon Day[, Year]-Mon Day, Year' range."""
    text = date_text.lower().replace(',', '').replace('–', '-')
    dates = [d.strip() for d in text.split('-')]
    if len(dates) != 2:
        raise ValueError(f"Unrecognized date format: {date_text!r}")
    # If the start token pair is "month day" rather than a complete "month
    # year", it's missing a year - borrow the end date's year
    start_tokens = dates[0].split()
    if len(start_tokens) == 2 and int(start_tokens[1]) <= 31:
        dates[0] = dates[0] + ' ' + dates[1].split()[-1]
    start_date = convert_date_to_dt(dates[0])
    end_date = convert_date_to_dt(dates[1])
    phase = 'future' if start_date and start_date > today else 'current'
    return phase, start_date, end_date

def scrape_walt_disney_family_museum(env='prod', region='sf'):
    """Scrape and process exhibitions from The Walt Disney Family Museum."""

    venue = 'The Walt Disney Family Museum'
    today = dt.date.today()
    # Events are keyed by name+venue (see processing.py), with no date
    # component, so a show that's been restaged under its original title
    # (e.g. "Awaking Beauty: The Art of Eyvind Earle" ran 2017-2018 and again
    # from 2026) collides with its own past run. Past exhibitions are
    # processed after upcoming ones, so without this the stale historical
    # entry would silently overwrite the one that's actually relevant now.
    current_or_upcoming_names = set()

    def process_article(article, phase_hint):
        title_tag = article.find('h2')
        link_tag = title_tag.find('a') if title_tag else None
        if not title_tag or not link_tag:
            logging.warning(f"Skipping exhibition with missing title/link at {venue}")
            return

        # get_text(' ', ...) because some titles split across adjacent text
        # nodes with no whitespace between them in the source HTML (e.g.
        # "<em>Walt Disney Treasures</em>Objects"). That same separator then
        # over-inserts a space before punctuation that glues onto the
        # previous node with none (e.g. "<em>it's a small world</em>: A..."),
        # so strip it back out before a few common punctuation marks.
        name = re.sub(r'\s+', ' ', title_tag.get_text(' ', strip=True))
        name = re.sub(r'\s+([:,.;])', r'\1', name)
        link = link_tag.get('href')
        if link and link.startswith('/'):
            link = BASE_URL + link

        date_div = article.select_one('.field-node--field-date-display-text-override')
        if not date_div:
            logging.warning(f"Skipping {name!r} at {venue}: no date field found")
            return

        date_text = extract_date_text(date_div)
        if date_text is None:
            # No parseable date line at all (e.g. a virtual exhibit just
            # labeled "Open Now") - keep it, dateless, under whichever
            # section the site itself filed it under. Not marked `ongoing`:
            # several of these sit in "Past Exhibitions" despite the "Open
            # Now" label, and ongoing=True there would be self-contradictory.
            phase = phase_hint or 'current'
            start_date = end_date = None
        else:
            try:
                if phase_hint == 'past':
                    # Already confirmed closed by the site's own "Past
                    # Exhibitions" listing - just need the dates, not a fresh
                    # phase decision.
                    _, start_date, end_date = parse_date_range(date_text, today)
                    phase = 'past'
                else:
                    phase, start_date, end_date = parse_date_range(date_text, today)
            except (KeyError, ValueError) as e:
                logging.warning(f"Could not parse dates for {name!r} at {venue}: {e}")
                return

        media = article.select_one('.media--blazy')
        image_src = media.get('data-src') if media else None
        image_link = (BASE_URL + image_src) if image_src and image_src.startswith('/') else image_src

        event_details = {
            'name': name,
            'venue': venue,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        if phase_hint != 'past':
            current_or_upcoming_names.add(name)
        elif name in current_or_upcoming_names:
            logging.info(f"Skipping past run of {name!r} at {venue}: currently showing again under the same title")
            return

        if env == 'dev':
            logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    # Page 1 (no ?page param) carries both the "Upcoming Exhibitions" section
    # (current + future shows) and the first page of "Past Exhibitions"; pages
    # 2-5 (?page=1..4) hold only more past exhibitions, confirmed via the
    # site's own pager (5 pages total).
    for page in range(0, 5):
        url = 'https://www.waltdisney.org/exhibitions' if page == 0 else f'https://www.waltdisney.org/exhibitions?page={page}'
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Could not fetch {venue} exhibitions page {page}; existing data kept.")
            continue

        if page == 0:
            upcoming_heading = soup.find('h2', class_='block-title', string=re.compile('Upcoming Exhibitions'))
            if upcoming_heading:
                for article in upcoming_heading.find_parent().find_all('article'):
                    process_article(article, phase_hint=None)

        past_heading = soup.find('h2', class_='block-title', string=re.compile('Past Exhibitions'))
        if not past_heading:
            break
        for article in past_heading.find_parent().find_all('article'):
            process_article(article, phase_hint='past')
