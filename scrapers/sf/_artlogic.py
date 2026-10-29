"""Shared reading of exhibition lists on Artlogic-built gallery sites.

These sites list each show as <li><a><div class="content"> with an h2 title,
a span.date written day-first ("5 Dec 2026 - 2 Jan 2027", "2 Oct - 19 Dec 2026"),
an optional span.location, and a span.description.
"""
import datetime as dt
import re
from urllib.parse import urljoin

_SIDE_RE = re.compile(r'(\d{1,2})\s+([A-Za-z]+)\.?(?:\s+(\d{4}))?')
_MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], start=1)}


def parse_day_first_range(text):
    """'2 Oct - 19 Dec 2026' -> (start, end). The end carries the year; a start
    without one takes it, rolling back a year if that would put it after the end.
    Returns (None, None) if the text isn't a day-first range."""
    parts = re.split(r'\s+[-–—]\s+', text.strip(), maxsplit=1)
    if len(parts) != 2:
        return None, None
    sides = []
    for part in parts:
        m = _SIDE_RE.search(part)
        month = _MONTHS.get(m.group(2)[:3].lower()) if m else None
        if not month:
            return None, None
        sides.append((int(m.group(1)), month, int(m.group(3)) if m.group(3) else None))
    (sd, sm, sy), (ed, em, ey) = sides
    if not ey:
        return None, None
    try:
        end = dt.date(ey, em, ed)
        start = dt.date(sy or ey, sm, sd)
        if not sy and start > end:
            start = dt.date(ey - 1, sm, sd)
    except ValueError:
        return None, None
    return start, end


def artlogic_items(soup, base_url):
    """Yield dicts (name, date_text, location, description, link) for each listed show."""
    for li in soup.select('li'):
        title = li.select_one('.content h2')
        date = li.select_one('.content .date')
        link = li.select_one('a[href]')
        if not (title and date and link):
            continue
        location = li.select_one('.content .location')
        description = li.select_one('.content .description')
        yield {
            'name': title.get_text(' ', strip=True),
            'date_text': date.get_text(' ', strip=True),
            'location': location.get_text(' ', strip=True) if location else '',
            'description': description.get_text(' ', strip=True) if description else None,
            'link': urljoin(base_url, link['href']),
        }
