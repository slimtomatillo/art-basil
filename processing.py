import json
from hashlib import md5
import datetime as dt
import logging
from zoneinfo import ZoneInfo
from config import DB_FILES, REGION_TIMEZONES
from utils import load_db, save_db

def generate_event_hash(event_details):
    event_string = json.dumps(event_details, sort_keys=True, default=str)
    return md5(event_string.encode('utf-8')).hexdigest()

def generate_unique_identifier(event_details):
    return f"{event_details['name']}-{event_details['venue']}"

def process_event(event_details, region):
    db = load_db(DB_FILES[region])
    site_events = db.get(event_details['venue'], {})
    event_id = generate_unique_identifier(event_details)
    event_hash = generate_event_hash(event_details)

    if event_id not in site_events or site_events[event_id]['hash'] != event_hash:
        logging.info(f"Updating event: {event_details['name']}")
        site_events[event_id] = {**event_details, 'hash': event_hash}
        db[event_details['venue']] = site_events
        save_db(db, region)

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
