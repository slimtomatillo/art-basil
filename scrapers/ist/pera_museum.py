from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging
import re
from urllib.parse import quote

# peramuzesi.org.tr is the Turkish-only twin of this site
BASE_URL = 'https://www.peramuseum.org'
CURRENT_URL = f'{BASE_URL}/Exhibition'
ARCHIVE_URL = f'{BASE_URL}/Exhibition/ListYears'

# The archive is one page per calendar year back to 2005; only keep roughly the last two years.
PAST_WINDOW_DAYS = 730
MAX_DESCRIPTION_CHARS = 500

MONTH_RE = '|'.join(sorted(MONTH_TO_NUM_DICT.keys(), key=len, reverse=True))
# "September 29, 2026 - March 28, 2027", "March 3 - June 4, 2025"
RANGE_RE = re.compile(
    rf'^(?P<m1>{MONTH_RE})\s+(?P<d1>\d{{1,2}})(?:,\s*(?P<y1>\d{{4}}))?\s*[–—-]\s*'
    rf'(?:(?P<m2>{MONTH_RE})\s+)?(?P<d2>\d{{1,2}}),\s*(?P<y2>\d{{4}})$',
    re.IGNORECASE
)


def parse_dates(text):
    """Return (start_date, end_date) from a card's date line; (None, None) when it has none."""
    text = ' '.join(text.replace('\xa0', ' ').split())
    if not text:
        return None, None
    try:
        match = RANGE_RE.match(text)
        if match:
            y2 = int(match.group('y2'))
            end_date = dt.date(y2, MONTH_TO_NUM_DICT[(match.group('m2') or match.group('m1')).lower()],
                               int(match.group('d2')))
            y1 = int(match.group('y1')) if match.group('y1') else y2
            start_date = dt.date(y1, MONTH_TO_NUM_DICT[match.group('m1').lower()], int(match.group('d1')))
            # "December 20 - January 10, 2027" - no explicit start year, so it began the year before
            if start_date > end_date and not match.group('y1'):
                start_date = start_date.replace(year=start_date.year - 1)
            return start_date, end_date
    except ValueError:
        pass
    logging.warning(f"Pera Museum: could not parse dates {text!r}")
    return None, None


def parse_cards(soup):
    """Return [{'title', 'subtitle', 'dates', 'description', 'href', 'image'}] for every exhibition card.

    The current listing and the yearly archive use slightly different markup
    (h3/p.card-text vs span.listtitle/span.listtarih), so each field has a fallback.
    """
    cards = []
    for card in soup.select('div.card'):
        link = card.find('a', href=re.compile(r'^/exhibition/', re.IGNORECASE))
        if not link:
            continue
        body = card.select_one('.card-body')
        if body is None:
            continue

        title_tag = body.select_one('h3.card-title, span.listtitle')
        title = ' '.join(title_tag.get_text(' ', strip=True).split()) if title_tag else None
        if not title:
            continue

        if body.select_one('h3.card-title'):
            paragraphs = [p for p in body.select('p.card-text') if p.find_parent('p') is None]
            texts = [' '.join(p.get_text(' ', strip=True).split()) for p in paragraphs]
            subtitle, dates, description = (texts + ['', '', ''])[:3]
        else:
            subtitle_tag = body.select_one('div.divSummary')
            subtitle = ' '.join(subtitle_tag.get_text(' ', strip=True).split()) if subtitle_tag else ''
            dates_tag = body.select_one('span.listtarih')
            dates = ' '.join(dates_tag.get_text(' ', strip=True).split()) if dates_tag else ''
            description_tag = body.select_one('div.listdetail')
            description = ' '.join(description_tag.get_text(' ', strip=True).split()) if description_tag else ''

        img = card.find('img', src=True)
        cards.append({
            'title': title,
            'subtitle': subtitle,
            'dates': dates,
            'description': description,
            'href': link['href'].strip(),
            'image': img['src'] if img else None,
        })
    return cards


def scrape_pera_museum_exhibitions(env='prod', region='ist'):
    """Scrape and process current and recent past exhibitions from Pera Museum."""

    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=PAST_WINDOW_DAYS)

    listings = []
    soup = fetch_and_parse(CURRENT_URL)
    if soup is None:
        logging.warning("Pera Museum: could not fetch the current exhibitions listing")
    else:
        listings.append(('current', parse_cards(soup)))
    for year in range(today.year, cutoff.year - 1, -1):
        archive = fetch_and_parse(f'{ARCHIVE_URL}/{year}')
        if archive is None:
            logging.warning(f"Pera Museum: could not fetch the {year} exhibition archive")
            continue
        listings.append(('past', parse_cards(archive)))

    if not any(cards for _, cards in listings):
        logging.warning("Pera Museum: no exhibitions found")
        return

    seen = set()
    for section_phase, cards in listings:
        for card in cards:
            if card['href'] in seen:
                continue
            seen.add(card['href'])

            start_date, end_date = parse_dates(card['dates'])

            if end_date and end_date < today:
                if end_date < cutoff:
                    continue
                phase = 'past'
            elif start_date and start_date > today:
                phase = 'future'
            else:
                phase = section_phase

            # Collection displays on the current listing carry no dates at all
            ongoing = phase == 'current' and not end_date

            description = ' '.join(filter(None, [card['subtitle'], card['description']]))
            if len(description) > MAX_DESCRIPTION_CHARS:
                description = description[:MAX_DESCRIPTION_CHARS].rsplit(' ', 1)[0] + '…'

            event_link = BASE_URL + quote(card['href'], safe='/')
            event_details = {
                'name': card['title'],
                'venue': 'Pera Museum',
                'description': description or None,
                'tags': ['exhibition', phase, 'museum'],
                'phase': phase,
                'dates': {'start': start_date, 'end': end_date},
                'ongoing': ongoing,
                'links': [{'link': event_link, 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if card['image']:
                image_url = card['image'] if card['image'].startswith('http') else BASE_URL + card['image']
                event_details['links'].append({'link': image_url, 'description': 'Image'})

            logging.info(f"Event details in dev - Name: {event_details.get('name')}, Venue: {event_details.get('venue')}")

            if env == 'prod':
                process_event(event_details, region)
