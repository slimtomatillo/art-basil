from utils import fetch_and_parse, load_db
from processing import process_event
from config import DB_FILES, MONTH_TO_NUM_DICT
from collections import Counter
import calendar
import datetime as dt
from datetime import timezone
import json
import logging
import re
import requests
from bs4 import BeautifulSoup

VENUE = 'Institute of Contemporary Art San José'
BASE_URL = 'https://www.icasanjose.org'
# The listing pages are built with the "Epic News Element" WordPress plugin;
# its "Load More" button POSTs here for each further page of results. (The
# standard WordPress REST API would be simpler, but it requires a login.)
LOAD_MORE_URL = f'{BASE_URL}/?epic-ajax-request=epic-ne'
# Hard stop for the archive walk in case the endpoint ever stops reporting
# `next: false` (39 pages as of Oct 2026, going back to 2006, growing ~1/yr).
MAX_ARCHIVE_PAGES = 100

# Longest names first so e.g. "june" matches before the "jun" abbreviation
# would otherwise eat only part of it.
_MONTH = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# A date range at the start of a line. The archive spans ~20 years of
# hand-typed listings, so nearly every part is optional:
#   "September 18, 2026 – February 21, 2027"   full
#   "April 7 - August 21, 2022"                start year omitted
#   "February 1 - 24, 2019"                    end month omitted
#   "November 18, 2022 - August 2024"          end day omitted
#   "September 14, 2024 - Ongoing"
# (ordinals like "31st" are stripped before matching). Anything after the
# range - a gallery name, the description - is ignored.
_RANGE_RE = re.compile(
    rf'(?P<sm>{_MONTH})\.?\s+(?P<sd>\d{{1,2}})\b(?:,?\s*(?P<sy>\d{{4}}))?'
    rf'\s*(?:[–—-]|to)\s*'
    rf'(?:(?P<ongoing>ongoing)'
    rf'|(?:(?P<em>{_MONTH})\.?\s+)?(?:(?P<ed>\d{{1,2}})\b)?(?:,?\s*(?P<ey>\d{{4}}))?)',
    re.IGNORECASE,
)


def parse_date_range(text):
    """Returns (start, end, ongoing) for a line beginning with a date range,
    or None if it doesn't begin with one."""
    text = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', ' '.join(text.split()))
    text = re.sub(r'(?i)^on view:\s*', '', text)
    match = _RANGE_RE.match(text)
    if not match:
        return None
    g = match.groupdict()
    start_month = MONTH_TO_NUM_DICT[g['sm'].lower()]
    start_day = int(g['sd'])

    if g['ongoing']:
        if not g['sy']:
            return None
        return dt.date(int(g['sy']), start_month, start_day), None, True

    end_month = MONTH_TO_NUM_DICT[g['em'].lower()] if g['em'] else start_month
    if not g['ed'] and not g['em']:
        return None  # nothing after the dash at all
    if g['ey']:
        end_year = int(g['ey'])
    elif g['sy']:
        end_year = int(g['sy']) + (1 if end_month < start_month else 0)
    else:
        return None  # no year anywhere
    # A month-only end date ("August 2024") runs through the end of that month
    end_day = int(g['ed']) if g['ed'] else calendar.monthrange(end_year, end_month)[1]

    if g['sy']:
        start_year = int(g['sy'])
    else:
        # Start year omitted - it's the end's year, unless the range wraps
        # past New Year ("August 6 - February 20, 2022" started in 2021)
        start_year = end_year - (1 if (start_month, start_day) > (end_month, end_day) else 0)

    try:
        start, end = dt.date(start_year, start_month, start_day), dt.date(end_year, end_month, end_day)
    except ValueError:
        return None  # e.g. a typo'd "February 30"
    if start > end:
        # A typo'd start year (seen: "November 8, 2104 - January 24, 2015") -
        # infer it from the end date as if it had been omitted
        start = start.replace(year=end_year - (1 if (start_month, start_day) > (end_month, end_day) else 0))
    return start, end, False


def scrape_event_page(event_url):
    """The listing only carries dates, so the description comes from the
    exhibition's own page: the first real paragraph of body text. The page
    leads with a few short lines (dates, opening-reception times, the title
    restated, a subtitle like "A public mural at ICA San José") in no fixed
    order, so skip anything that's short or starts with a date. Also returns
    the page's date range, for the archive entries whose listing has none.
    Returns (description, dates) where dates is parse_date_range's tuple or None."""
    soup = fetch_and_parse(event_url)
    if soup is None:
        logging.warning(f"Could not fetch {VENUE} event page: {event_url}")
        return None, None
    content = soup.find(class_='entry-content')
    if not content:
        return None, None
    description = dates = None
    for p in content.find_all('p'):
        # No separator: inline tags can split mid-word ("experienc<span>e"),
        # and the source HTML already has its own spaces between words.
        text = ' '.join(p.get_text().split())
        parsed = parse_date_range(text)
        if parsed and not dates:
            dates = parsed
        elif not parsed and not description and len(text) >= 100:
            description = text
    return description, dates


def parse_listing(soup):
    """Pull the raw (title, link, date-line, image) out of each listing card."""
    items = []
    for article in soup.select('article.jeg_post'):
        title_tag = article.select_one('h3.jeg_post_title a')
        if not title_tag:
            logging.warning(f"Skipping {VENUE} exhibition with missing title/link")
            continue
        excerpt = article.select_one('.jeg_post_excerpt p')
        # Lazy-loaded: the real image URL is in data-src, src is a placeholder
        img_tag = article.select_one('.jeg_thumb img')
        items.append({
            'name': title_tag.get_text(' ', strip=True),
            'link': title_tag.get('href'),
            'date_text': excerpt.get_text(' ', strip=True) if excerpt else '',
            'image': img_tag.get('data-src') if img_tag else None,
        })
    return items


def fetch_archive_pages(first_page, known_links):
    """Follow the archive's "Load More" button until reaching a page with a
    show in `known_links` (already stored). The archive is newest-first and
    past shows don't change, so everything from there back is already
    captured - walking all ~40 pages every day would be wasted requests.
    ("Any" rather than "all": a show that's never stored, e.g. one with no
    dates anywhere, would otherwise keep the walk going every day.) With an
    empty `known_links` (first run) this walks to the end. The plugin needs
    the listing module's full settings object echoed back, which the first
    page embeds as `var epic_module_<id> = {...};`."""
    module = first_page.select_one('.jeg_postblock[data-unique]')
    settings_match = module and re.search(
        rf"var {re.escape(module['data-unique'])} = (\{{.*?\}});</script>", str(first_page))
    if not settings_match:
        logging.warning(f"{VENUE} archive: Load More settings not found; only the first page was scraped")
        return []
    settings = json.loads(settings_match.group(1))

    items = []
    for page in range(2, MAX_ARCHIVE_PAGES + 1):
        data = {
            'action': f"epic_module_ajax_{settings['class']}",
            'module': 'true',
            'data[filter]': '0',
            'data[filter_type]': 'all',
            'data[current_page]': str(page),
        }
        data.update({f'data[attribute][{k}]': v for k, v in settings.items()})
        try:
            response = requests.post(LOAD_MORE_URL, data=data, headers={'User-Agent': 'Your Bot 0.1'}, timeout=(10, 30))
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as e:
            logging.warning(f"{VENUE} archive page {page} failed ({e}); keeping the {len(items)} older shows fetched so far")
            break
        page_items = parse_listing(BeautifulSoup(result.get('content', ''), 'html.parser'))
        items += page_items
        if not result.get('next') or any(item['link'] in known_links for item in page_items):
            break
    return items


def scrape_ica_san_jose(env='prod', region='sf'):
    """Scrape and process exhibitions from the Institute of Contemporary Art San José."""

    # Detail pages (for descriptions, and dates the listing lacks) are one
    # request per show - ~150 for the full archive - and old shows never
    # change, so reuse what's already stored rather than refetching daily.
    # Matched on the event page URL, which (unlike the title) is unique.
    stored = load_db(DB_FILES[region]).get(VENUE, {}) if env == 'prod' else {}
    stored_by_link = {link['link']: event for event in stored.values()
                      for link in event.get('links', []) if link.get('description') == 'Event Page'}

    listings = []  # (phase, item)
    for url, phase in [
        (f'{BASE_URL}/exhibitions/current-exhibitions/', 'current'),
        (f'{BASE_URL}/exhibitions/upcoming-exhibitions/', 'future'),
        (f'{BASE_URL}/exhibitions/archive/', 'past'),
    ]:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"Could not fetch {VENUE} {phase} exhibitions; existing data kept.")
            continue
        items = parse_listing(soup)
        # Current and upcoming each fit on one page; only the archive pages
        if phase == 'past':
            items += fetch_archive_pages(soup, stored_by_link.keys())
        listings += [(phase, item) for item in items]

    # Events are keyed by title, and the archive reuses some across years
    # ("Lift Off" is an annual MFA show) - repeats get a year suffix below so
    # they don't overwrite each other. Counted across stored shows too, since
    # the archive walk usually stops before reaching the older ones.
    title_by_link = {link: re.sub(r' \(\d{4}\)$', '', event['name']) for link, event in stored_by_link.items()}
    title_by_link.update({item['link']: item['name'] for _, item in listings})
    name_counts = Counter(title_by_link.values())

    for phase, item in listings:
        name = item['name']
        cached = stored_by_link.get(item['link'])

        description = cached.get('description') if cached else None
        dates = parse_date_range(item['date_text'])
        if not dates and cached and (cached['dates'].get('start') or cached['dates'].get('end')):
            start, end = cached['dates'].get('start'), cached['dates'].get('end')
            dates = (dt.date.fromisoformat(start[:10]) if start else None,
                     dt.date.fromisoformat(end[:10]) if end else None,
                     cached.get('ongoing', False))
        if not description or not dates:
            page_description, page_dates = scrape_event_page(item['link'])
            description = description or page_description
            dates = dates or page_dates
        if not dates:
            logging.warning(f"Skipping {name!r} at {VENUE}: no dates on its listing or its page")
            continue
        start_date, end_date, ongoing = dates
        # Only meaningful for a currently-on-view show - "ongoing" on a
        # past/upcoming listing would be a self-contradiction.
        ongoing = ongoing and phase == 'current'

        if name_counts[name] > 1:
            name = f"{name} ({(start_date or end_date).year})"

        event_details = {
            'name': name,
            'venue': VENUE,
            'description': description,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing,
            'links': [{'link': item['link'], 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if item['image']:
            event_details['links'].append({'link': item['image'], 'description': 'Image'})

        if env == 'dev':
            logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)
