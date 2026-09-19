import datetime as dt
from datetime import timezone
import html
import logging
import re

import requests
from bs4 import BeautifulSoup

from config import MONTH_TO_NUM_DICT
from processing import process_event

# Madrone Art Bar runs its site on WordPress. Querying the REST API directly
# for the "Exhibitions" category is far more reliable than scraping the
# rendered HTML of /exhibitions/ or the "Previous Exhibitions" monthly-archive
# widget (that archive isn't filtered to exhibitions - it mixes in every blog
# post from that month).
API_URL = 'https://madroneartbar.com/wp-json/wp/v2/posts'
EXHIBITIONS_CATEGORY_ID = 8

# The exhibitions category goes back to 2019 and not every older post states
# a parseable date range. Match the approach used for MOCA (LA): pull
# current + upcoming exhibitions, plus past ones from roughly the last two
# years, rather than chasing every historical phrasing back to 2019.
PAST_WINDOW_DAYS = 730

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# Matches "September 30th to November 23rd 2026", "December 1, 2025, to
# January 30th, 2026", etc. The year groups tolerate a stray embedded space
# (e.g. "202 6") that shows up on a few posts where the year is split across
# HTML elements.
DATE_RANGE_RE = re.compile(
    rf'(?P<m1>{MONTH_RE})\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?,?\s*'
    rf'(?:(?P<y1>\d{{4}}|\d{{3}}\s?\d),?\s*)?'
    rf'(?:to|[-–—])\s*'
    rf'(?P<m2>{MONTH_RE})\.?\s+(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?,?\s*'
    rf'(?P<y2>\d{{4}}|\d{{3}}\s?\d)?',
    re.IGNORECASE
)
OPENING_RE = re.compile(r'opening (party|event|reception)', re.IGNORECASE)


def fetch_exhibition_posts():
    """Fetch all posts in the Exhibitions category via the WP REST API."""
    try:
        response = requests.get(
            API_URL,
            params={'categories': EXHIBITIONS_CATEGORY_ID, 'per_page': 100, '_embed': 1},
            headers={'User-Agent': 'Your Bot 0.1'},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching Madrone Art Bar exhibitions: {e}")
        return []
    return response.json()


def parse_date_range(text, publish_year):
    """Extract (start_date, end_date) from free text, or (None, None)."""
    match = DATE_RANGE_RE.search(text)
    if not match:
        return None, None

    y1 = (match.group('y1') or match.group('y2') or publish_year)
    y2 = (match.group('y2') or y1)
    y1, y2 = str(y1).replace(' ', ''), str(y2).replace(' ', '')

    try:
        start_date = dt.date(int(y1), MONTH_TO_NUM_DICT[match.group('m1').lower()], int(match.group('d1')))
        end_date = dt.date(int(y2), MONTH_TO_NUM_DICT[match.group('m2').lower()], int(match.group('d2')))
    except ValueError as e:
        logging.warning(f"Madrone Art Bar: could not build date from match {match.group()!r}: {e}")
        return None, None

    # A range like "Feb 1 to Apr 8" with no explicit year rolls into the next
    # calendar year if the end month precedes the start month.
    if end_date < start_date:
        end_date = end_date.replace(year=end_date.year + 1)

    return start_date, end_date


def compute_phase(start_date, end_date, today):
    if end_date and end_date < today:
        return 'past'
    elif start_date and start_date > today:
        return 'future'
    elif start_date or end_date:
        return 'current'
    return None


def scrape_madrone_art_bar(env='prod', region='sf'):
    """Scrape and process exhibitions from Madrone Art Bar (SF)."""

    posts = fetch_exhibition_posts()
    if not posts:
        logging.warning("Madrone Art Bar: no exhibition posts returned")
        return

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)

    for post in posts:
        title = html.unescape(post.get('title', {}).get('rendered', '')).strip()
        if not title:
            continue

        content_html = post.get('content', {}).get('rendered', '')
        content_text = re.sub(r'\s+', ' ', BeautifulSoup(content_html, 'html.parser').get_text(' ', strip=True))

        publish_year = post.get('date', '')[:4]
        start_date, end_date = parse_date_range(content_text, publish_year)

        # Skip old posts we couldn't date and that are outside the window;
        # for undated posts, use the publish date as a rough stand-in so we
        # still surface anything recent.
        reference_date = end_date or start_date or (
            dt.datetime.strptime(post['date'][:10], '%Y-%m-%d').date() if post.get('date') else None
        )
        still_upcoming = start_date and start_date > today
        if reference_date and reference_date < cutoff and not still_upcoming:
            continue

        phase = compute_phase(start_date, end_date, today)

        excerpt_html = post.get('excerpt', {}).get('rendered', '')
        description = BeautifulSoup(excerpt_html, 'html.parser').get_text(' ', strip=True)
        description = html.unescape(re.sub(r'\s+', ' ', description)).strip()

        tags = ['exhibition']
        if phase:
            tags.append(phase)
        if OPENING_RE.search(content_text):
            tags.append('opening')

        event_details = {
            'name': title,
            'venue': 'Madrone Art Bar',
            'description': description,
            'tags': tags,
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': False,
            'links': [{'link': post['link'], 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        featured_media = post.get('_embedded', {}).get('wp:featuredmedia')
        if featured_media and featured_media[0].get('source_url'):
            event_details['links'].append({'link': featured_media[0]['source_url'], 'description': 'Image'})

        if env == 'dev':
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

        if env == 'prod':
            process_event(event_details, region)
