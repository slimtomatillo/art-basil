from utils import fetch_and_parse
from processing import process_event
import datetime as dt
from datetime import timezone
import logging

BASE_URL = 'https://www.nortonsimon.org'
# Norton Simon's Cloudflare setup 403s the default bot User-Agent, so present a
# browser one for this venue.
BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}
# "Exhibitions on view" (current + upcoming) and the 2020s archive page
LISTING_URLS = [
    ('https://www.nortonsimon.org/exhibitions/current', 'current'),
    ('https://www.nortonsimon.org/exhibitions/2020-2029', 'past'),
]


def parse_date_range(text):
    """Parse 'Month D, YYYY - Month D, YYYY' (or a single date) into two dates.

    Handles a missing year on the left side ('May 18 - September 4, 2026') by
    borrowing the year from the right side. Returns (start_date, end_date),
    either of which may be None.
    """
    if not text:
        return None, None
    cleaned = ' '.join(text.split()).replace('–', '-').replace('—', '-')
    parts = [p.strip(' ,') for p in cleaned.split('-')]

    def to_date(piece, fallback_year=None):
        piece = piece.strip(' ,')
        if not piece:
            return None
        for fmt in ('%B %d, %Y', '%B %d %Y', '%b %d, %Y'):
            try:
                return dt.datetime.strptime(piece, fmt).date()
            except ValueError:
                pass
        if fallback_year:
            for fmt in ('%B %d', '%b %d'):
                try:
                    parsed = dt.datetime.strptime(piece, fmt)
                    return dt.date(fallback_year, parsed.month, parsed.day)
                except ValueError:
                    pass
        return None

    if len(parts) == 1:
        return to_date(parts[0]), None

    end_date = to_date(parts[-1])
    year = end_date.year if end_date else None
    start_date = to_date(parts[0], fallback_year=year)
    return start_date, end_date


def absolute_url(href):
    if not href:
        return None
    return href if href.startswith('http') else BASE_URL + href


def extract_items(soup):
    """Yield (title, link, date_text, image, description) for each exhibition
    on a listing page. The 'current' page uses .exhibition-item blocks; the
    archive page uses .collection-item blocks."""
    for item in soup.select('.exhibition-item'):
        time_tag = item.select_one('.desc-text .time')
        name_tag = item.select_one('.desc-text strong.name a, .desc-text .name a, .desc-text .name')
        if not time_tag or not name_tag:
            continue  # skip the "no exhibitions on view" placeholder
        link_tag = item.select_one('.img-wrap a[href]') or (name_tag if name_tag.has_attr('href') else None)
        img_tag = item.select_one('.img-wrap img')
        yield (
            name_tag.get_text(strip=True),
            absolute_url(link_tag['href']) if link_tag and link_tag.has_attr('href') else None,
            time_tag.get_text(' ', strip=True),
            absolute_url(img_tag['src']) if img_tag and img_tag.has_attr('src') else None,
            None,
        )

    for item in soup.select('.collection-item'):
        heading = item.select_one('.desc-text h4')
        if not heading:
            continue
        name_tag = heading.find('a')
        small = heading.find('small')
        img_tag = item.select_one('.img-holder img')
        desc_tag = item.select_one('.desc-text > div p')
        yield (
            (name_tag.get_text(strip=True) if name_tag else heading.get_text(strip=True)),
            absolute_url(name_tag['href']) if name_tag and name_tag.has_attr('href') else None,
            small.get_text(' ', strip=True) if small else None,
            absolute_url(img_tag['src']) if img_tag and img_tag.has_attr('src') else None,
            desc_tag.get_text(strip=True) if desc_tag else None,
        )


def scrape_norton_simon_exhibitions(env='prod', region='la'):
    """Scrape and process exhibitions from the Norton Simon Museum."""

    today = dt.datetime.now().date()
    seen_links = set()

    for url, _default_phase in LISTING_URLS:
        soup = fetch_and_parse(url, headers=BROWSER_HEADERS)
        if soup is None:
            logging.warning(f"Error scraping Norton Simon exhibitions ({url}) --> no soup found")
            continue

        for title, link, date_text, image, description in extract_items(soup):
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)

            start_date, end_date = parse_date_range(date_text)

            if end_date and end_date < today:
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            else:
                phase = 'current'

            event_details = {
                'name': title,
                'venue': 'Norton Simon Museum',
                'description': description,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': False,
                'links': [{'link': link, 'description': 'Event Page'}] if link else [],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if image:
                event_details['links'].append({'link': image, 'description': 'Image'})

            # Add logging for dev environment
            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            # Process event in prod environment
            if env == 'prod':
                process_event(event_details, region)
