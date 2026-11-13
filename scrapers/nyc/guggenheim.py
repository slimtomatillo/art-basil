"""Solomon R. Guggenheim Museum, 1071 Fifth Ave: the exhibitions on its listing page.

https://www.guggenheim.org/exhibitions is a Vue page, but it carries its data in the HTML: a script holds
`const bootstrap = {...}` and under initial.main.posts.featuredExhibitions the lists on_view and upcoming (and
past, which is not read). Each item has a title (with <br> between the lines), dates as {day, month, year},
a short excerpt, the picture and the slug of its page. A show marked "Ongoing" (the Thannhauser Collection, with an
old end date) is a permanent display and is left out.
"""
import datetime as dt
import json
import logging
import re
from urllib.parse import urljoin

from processing import region_today
from scrapers.nyc._common import clean, strip_tags
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://www.guggenheim.org/exhibitions'
SHOW_URL = 'https://www.guggenheim.org/exhibition/'
VENUE = 'Guggenheim Museum'
_MAX_DESCRIPTION = 400


def _day(part):
    """A date from {"day": "15", "month": "March", "year": "2024"}, or None."""
    try:
        return dt.datetime.strptime(f"{part['day']} {part['month']} {part['year']}", '%d %B %Y').date()
    except (KeyError, TypeError, ValueError):
        return None


def _exhibitions(soup):
    """The on_view and upcoming items from the page's bootstrap data, or []."""
    for script in soup.find_all('script'):
        text = script.string or ''
        start = text.find('const bootstrap = ')
        if start < 0:
            continue
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start + len('const bootstrap = '):])
            posts = data['initial']['main']['posts']['featuredExhibitions']
        except (ValueError, KeyError, TypeError):
            return []
        return [item for section in ('on_view', 'upcoming') for item in (posts.get(section) or {}).get('items') or []]
    return []


def _title(raw):
    """The title: its lines (separated by <br>) joined with ": ", and a title set in capitals ("TARYN SIMON<br>FATHER
    COUNTRY") in title case."""
    parts = [strip_tags(part) for part in re.split(r'<br\s*/?>', str(raw or ''), flags=re.IGNORECASE)]
    parts = [part.title() if part.isupper() else part for part in parts if part]
    return ': '.join(parts).replace(' | ', ': ')


def scrape_guggenheim(env='prod', region='nyc'):
    """Scrape and process the Guggenheim's current and upcoming exhibitions."""
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Guggenheim: could not fetch the exhibitions page; existing data kept.")
        return
    items = _exhibitions(soup)
    found = 0
    seen = set()
    for item in items:
        dates = item.get('dates') or {}
        if (dates.get('label') or '').strip().lower() == 'ongoing':
            continue
        start_date, end_date = _day(dates.get('start')), _day(dates.get('end'))
        name = _title(item.get('title'))
        slug = item.get('slug')
        if not (name and slug and (start_date or end_date)):
            continue
        description = strip_tags(item.get('excerpt')) or None
        if description and len(description) > _MAX_DESCRIPTION:
            description = description[:_MAX_DESCRIPTION].rsplit(' ', 1)[0]
        picture = (item.get('featuredImage') or {}).get('sourceUrl')
        image = urljoin(PAGE_URL, picture) if picture else None
        found += publish(env, region, VENUE, name, start_date, end_date, SHOW_URL + slug, tag='museum',
                         description=description, seen=seen, image=image)
    if not found:
        logging.warning("Guggenheim: no current or upcoming exhibition found; existing data kept.")
