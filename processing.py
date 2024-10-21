import json
from hashlib import md5
import datetime as dt
import logging
from utils import load_db, save_db

def generate_event_hash(event_details):
    event_string = json.dumps(event_details, sort_keys=True, default=str)
    return md5(event_string.encode('utf-8')).hexdigest()

def generate_unique_identifier(event_details):
    return f"{event_details['name']}-{event_details['venue']}"

def process_event(event_details):
    db = load_db()
    site_events = db.get(event_details['venue'], {})
    event_id = generate_unique_identifier(event_details)
    event_hash = generate_event_hash(event_details)

    if event_id not in site_events or site_events[event_id]['hash'] != event_hash:
        logging.info(f"Updating event: {event_details['name']}")
        site_events[event_id] = {**event_details, 'hash': event_hash}
        db[event_details['venue']] = site_events
        save_db(db)

def update_event_phases():
    db = load_db()
    today = dt.datetime.now().date()
    for venue, events in db.items():
        for event_key, event in events.items():
            try:
                end_date_str = event['dates'].get('end')
                end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                if end_date and end_date < today:
                    event['phase'] = 'past'
                    event['ongoing'] = False
                    event['tags'] = [tag for tag in event['tags'] if tag != 'current']
                    if 'past' not in event['tags']:
                        event['tags'].append('past')
            except ValueError as e:
                logging.error(f"Error processing event '{event_key}': {e}")
    save_db(db)
