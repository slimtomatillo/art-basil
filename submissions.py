"""Add manually-submitted events (from the email/form submission process) to the database.

Unlike the scrapers, submissions come from people, so this module validates input
and checks for likely duplicates before writing anything.
"""

import argparse
import datetime as dt
import difflib
import json
import sys
from datetime import timezone

from config import DB_FILES
from processing import process_event, generate_unique_identifier
from utils import load_db, save_db

DUPLICATE_MATCH_THRESHOLD = 0.6


class SubmissionError(Exception):
    pass


def compute_phase(start_date, end_date, today=None):
    today = today or dt.datetime.today().date()
    if start_date and end_date:
        if start_date <= today <= end_date:
            return 'current'
        elif start_date > today:
            return 'future'
        else:
            return 'past'
    return None


def find_likely_duplicates(region, venue, name):
    """Return existing event names at this venue that closely match `name`."""
    db = load_db(DB_FILES[region])
    existing = db.get(venue, {})
    matches = []
    for event in existing.values():
        ratio = difflib.SequenceMatcher(None, name.lower(), event['name'].lower()).ratio()
        if ratio >= DUPLICATE_MATCH_THRESHOLD:
            matches.append((event['name'], round(ratio, 2)))
    return sorted(matches, key=lambda m: -m[1])


def add_submission(region, name, venue, start_date, end_date, description='',
                    tags=None, links=None, venue_address=None, ongoing=False,
                    force=False):
    """Validate, dedup-check, and write a submitted event.

    start_date / end_date: dt.date or None.
    tags: list of tags (e.g. ['exhibition', 'opening', 'free']); the phase
        ('future'/'current'/'past') is added automatically if not present.
    links: list of {'link': url, 'description': label} dicts. Include an
        entry with description 'Event Page' for the primary source.
    venue_address: required the first time a venue is submitted; ignored
        (with a warning) if the venue already exists with a different address.
    force: skip the duplicate check and write anyway.
    """
    venues = load_db(DB_FILES[region].replace('_events.json', '_venues.json'))
    if venue not in venues:
        if not venue_address:
            raise SubmissionError(
                f"'{venue}' isn't a known venue yet. Pass venue_address to add it."
            )
        venues[venue] = venue_address
        save_venues(region, venues)
        print(f"Added new venue: {venue} ({venue_address})")
    elif venue_address and venues[venue] != venue_address:
        print(f"Note: venue '{venue}' already exists with address "
              f"'{venues[venue]}' — leaving it as-is, not overwriting with "
              f"'{venue_address}'.")

    if not force:
        dupes = find_likely_duplicates(region, venue, name)
        if dupes:
            dupe_list = ', '.join(f"'{n}' ({r})" for n, r in dupes)
            raise SubmissionError(
                f"Possible duplicate(s) at '{venue}': {dupe_list}. "
                f"Check them, then pass force=True if this is genuinely new."
            )

    phase = compute_phase(start_date, end_date)
    tags = list(tags or ['exhibition'])
    if phase and phase not in tags:
        tags.append(phase)

    event_details = {
        'name': name,
        'venue': venue,
        'description': description,
        'tags': tags,
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': ongoing,
        'links': links or [],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

    process_event(event_details, region)
    event_id = generate_unique_identifier(event_details)
    print(f"Added event: {event_id} (phase: {phase})")
    return event_id


def save_venues(region, venues):
    venues_path = DB_FILES[region].replace('_events.json', '_venues.json')
    with open(venues_path, 'w') as f:
        json.dump(venues, f, indent=4, default=str)


def _parse_date(value):
    if not value:
        return None
    return dt.datetime.strptime(value, '%Y-%m-%d').date()


def main():
    parser = argparse.ArgumentParser(description='Add a submitted event to the database.')
    parser.add_argument('--json', help='Path to a JSON file with the submission fields '
                                        '(see SUBMISSIONS.md for the schema)')
    parser.add_argument('--force', action='store_true', help='Skip the duplicate check')
    args = parser.parse_args()

    if not args.json:
        parser.error('Pass --json path/to/submission.json (interactive mode not supported yet)')

    with open(args.json) as f:
        data = json.load(f)

    try:
        add_submission(
            region=data['region'],
            name=data['name'],
            venue=data['venue'],
            start_date=_parse_date(data.get('start_date')),
            end_date=_parse_date(data.get('end_date')),
            description=data.get('description', ''),
            tags=data.get('tags'),
            links=data.get('links'),
            venue_address=data.get('venue_address'),
            ongoing=data.get('ongoing', False),
            force=args.force,
        )
    except SubmissionError as e:
        print(f"Not added: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
