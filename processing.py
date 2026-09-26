import difflib
import json
from hashlib import md5
import datetime as dt
import logging
import re
import unicodedata
from zoneinfo import ZoneInfo
from config import DB_FILES, REGION_TIMEZONES
from utils import load_db, save_db

def generate_event_hash(event_details):
    event_string = json.dumps(event_details, sort_keys=True, default=str)
    return md5(event_string.encode('utf-8')).hexdigest()

def generate_unique_identifier(event_details):
    return f"{event_details['name']}-{event_details['venue']}"

# Events are keyed by "name-venue", so when a source retitles a show ("and" -> "&",
# a subtitle added, an accent dropped) the scraper writes a second entry and the old
# one, never refreshed again, lingers as a duplicate. These helpers recognise the same
# event under a different title so it can be replaced rather than duplicated.
MIN_TITLE_SIMILARITY = 0.5


def normalize_title(name):
    """Lowercase, accent-free, '&' as 'and', punctuation collapsed to single spaces."""
    text = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', text.replace('&', 'and')).strip()


def _page_link(event):
    for link in event.get('links') or []:
        if link.get('description') == 'Event Page' and link.get('link'):
            return re.sub(r'^https?://(www\.)?', '', link['link'].rstrip('/').lower())
    return None


def _as_date(value):
    # scrapers pass date objects; stored events hold 'YYYY-MM-DD' (sometimes with a time)
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.datetime.strptime(value[:10], '%Y-%m-%d').date() if isinstance(value, str) and value else None


def _dates(event):
    dates = event.get('dates') or {}
    return _as_date(dates.get('start')), _as_date(dates.get('end'))


def _date_ranges_conflict(a, b):
    """True only if both events have dates and their ranges don't overlap."""
    (a_start, a_end), (b_start, b_end) = _dates(a), _dates(b)
    if not (a_start or a_end) or not (b_start or b_end):
        return False
    a_lo, a_hi = a_start or a_end, a_end or a_start
    b_lo, b_hi = b_start or b_end, b_end or b_start
    return not (a_lo <= b_hi and b_lo <= a_hi)


def is_same_event(a, b):
    """Whether two entries at one venue are the same event under different titles.

    Deliberately conservative - wrongly merging distinct shows deletes real data, while
    missing a duplicate just leaves the row that was already there. Sibling shows in a
    series ("Archive Room: X" / "Archive Room: Y") share dates and similar titles, so
    similarity plus dates is never enough on its own. Either:
    - the same event page, a compatible title (similar, or a blank one) and date
      ranges that don't conflict; or
    - an identical normalized title and identical start and end dates.
    """
    title_a, title_b = normalize_title(a.get('name')), normalize_title(b.get('name'))

    page = _page_link(a)
    if page and page == _page_link(b) and not _date_ranges_conflict(a, b):
        if not title_a or not title_b or difflib.SequenceMatcher(None, title_a, title_b).ratio() >= MIN_TITLE_SIMILARITY:
            return True

    (a_start, a_end), (b_start, b_end) = _dates(a), _dates(b)
    return bool(title_a) and title_a == title_b and bool(a_start and a_end) and (a_start, a_end) == (b_start, b_end)


# Events process_event has handled in this process. A scrape only replaces entries the
# source didn't list this run, so two live shows that merely look alike are never merged.
_processed_this_run = set()


def process_event(event_details, region):
    db = load_db(DB_FILES[region])
    venue = event_details['venue']
    site_events = db.get(venue, {})
    event_id = generate_unique_identifier(event_details)
    event_hash = generate_event_hash(event_details)
    _processed_this_run.add((region, venue, event_id))

    if event_id not in site_events or site_events[event_id]['hash'] != event_hash:
        logging.info(f"Updating event: {event_details['name']}")
        # An untitled incoming event (a scraper that failed to read the title) must never
        # replace a titled entry
        if event_id not in site_events and normalize_title(event_details.get('name')):
            for old_key, old_event in list(site_events.items()):
                if (region, venue, old_key) not in _processed_this_run and is_same_event(event_details, old_event):
                    logging.info(f"Database cleanup: replacing renamed event {old_event.get('name')!r} "
                                 f"with {event_details['name']!r}")
                    del site_events[old_key]
        site_events[event_id] = {**event_details, 'hash': event_hash}
        db[venue] = site_events
        save_db(db, region)


def dedupe_db(db):
    """Collapse entries that are the same event under different titles, keeping the
    titled, most recently refreshed one in each group. Mutates `db`; returns [(venue, removed_key, kept_key)]."""
    removed = []
    for venue, events in db.items():
        keys = list(events)
        parent = {key: key for key in keys}

        def find(key):
            while parent[key] != key:
                parent[key] = parent[parent[key]]
                key = parent[key]
            return key

        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if is_same_event(events[a], events[b]):
                    parent[find(a)] = find(b)

        groups = {}
        for key in keys:
            groups.setdefault(find(key), []).append(key)
        for group in groups.values():
            if len(group) > 1:
                # a titled entry beats an untitled one, then the most recently refreshed wins
                keep = max(group, key=lambda k: (bool(normalize_title(events[k].get('name'))), events[k].get('last_updated') or ''))
                for key in group:
                    if key != keep:
                        del events[key]
                        removed.append((venue, key, keep))
    return removed


PHASES = ('future', 'current', 'past')
PHASE_ORDER = {phase: i for i, phase in enumerate(PHASES)}


def region_today(region, now=None):
    """Today's date in the region's time zone (where its venues are)."""
    if region not in REGION_TIMEZONES:
        raise KeyError(f"No time zone for region '{region}'; add it to REGION_TIMEZONES in config.py")
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.astimezone(ZoneInfo(REGION_TIMEZONES[region])).date()


def derive_phase(start_date, end_date, today):
    """Phase implied by an event's dates, or None if it has none."""
    if end_date and end_date < today:
        return 'past'
    if start_date and start_date > today:
        return 'future'
    if start_date or end_date:
        return 'current'
    return None


def _parse_date(value):
    # Some sources store a trailing time ("2025-01-01 00:00:00"); only the day matters
    return dt.datetime.strptime(value[:10], '%Y-%m-%d').date() if value else None


def set_phase(event, phase):
    event['phase'] = phase
    event['tags'] = [tag for tag in event['tags'] if tag not in PHASES] + [phase]
    if phase == 'past':
        event['ongoing'] = False


def update_event_phases(db, region, now=None):
    """Advance each event's phase to match its dates, in the region's time zone.

    Phases only move forward (future -> current -> past). Dates can show an event
    has moved on, but never revive one already marked past: a source can list a
    show as past without recording an end date. Scrapers recompute phases from
    their own listings each run; this covers events they don't - manually entered
    ones, and scraped ones that dropped off their listing.
    """
    today = region_today(region, now)
    for venue, events in db.items():
        for event_key, event in events.items():
            try:
                derived = derive_phase(_parse_date(event['dates'].get('start')),
                                       _parse_date(event['dates'].get('end')), today)
                if derived and PHASE_ORDER[derived] > PHASE_ORDER.get(event.get('phase'), -1):
                    set_phase(event, derived)
            except Exception as e:
                logging.error(f"[Error processing event '{event_key}': {e}")
    save_db(db, region)
