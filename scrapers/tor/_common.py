"""Shared pieces for the Toronto venue scrapers: reading a page as text lines and
publishing one exhibition, so each venue module only has to say where its titles
and date ranges sit in the page."""
import datetime as dt
import logging
import re
from datetime import timezone

from processing import process_event, derive_phase, region_today


def page_lines(soup):
    """The page's visible text as a list of whitespace-normalised, non-empty lines."""
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return [re.sub(r'\s+', ' ', l).strip() for l in soup.get_text('\n').split('\n') if l.strip()]


def publish(env, region, venue, name, start_date, end_date, link, tag='gallery', description=None,
            keep_past=False, seen=None, kind='exhibition', extra_tags=()):
    """Build and store one exhibition (or, with kind='event', one program). Returns True if it
    was published (past entries are skipped unless keep_past, and a (name, start) pair already
    in `seen` is skipped)."""
    today = region_today(region)
    # A show that only says "Until <date>" has no start date; one with neither date can't be placed
    if not (name and (start_date or end_date)):
        return False
    key = (name, start_date)
    if seen is not None:
        if key in seen:
            return False
        seen.add(key)
    phase = derive_phase(start_date, end_date, today) or 'current'
    if phase == 'past' and not keep_past:
        return False
    event_details = {
        'name': name,
        'venue': venue,
        'description': description,
        'tags': [kind] + [phase] + [tag] + list(extra_tags),
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': False,
        'links': [{'link': link, 'description': 'Event Page'}],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if env == 'dev':
        logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {venue}")
    if env == 'prod':
        process_event(event_details, region)
    return True
