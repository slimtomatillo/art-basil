"""Give every venue address a latitude and longitude (WEBSITE-58, the foundation of the map and "Near me").

The venues files (docs/data/<region>_venues.json) hold street addresses. The map and the distances
need coordinates, and visitors' browsers should never have to look addresses up, so they are found
once, here, and kept in docs/data/venue_coordinates.json:

    {"sf": {"Venue Name": [{"lat": 37.7749, "lng": -122.4194}]}}

The list is in the same order as the venue's addresses (one entry for a plain address, one per space
for a venue with several). An entry can also carry:
    "approx": true   the geocoder only matched the street or the area, not the building: check it
    "manual": true   set by hand; this script never touches it again

Run it after adding a venue (ADDING_A_REGION.md, 1c). It only looks up addresses that have no entry yet,
so it is quick, and it uses OpenStreetMap's public Nominatim service at the rate its usage policy allows
(one request a second, with an identifying User-Agent, results kept in the repo so nothing is asked twice):

    python geocode_venues.py                      # every address without coordinates
    python geocode_venues.py --region sf          # one region
    python geocode_venues.py --redo "Venue Name"  # look a venue up again (not a "manual" one)
    python geocode_venues.py --dry-run            # show what would be looked up, ask nothing

Afterwards it lists what it could not find and what was matched only roughly. Fix those by editing
docs/data/venue_coordinates.json by hand (set "manual": true), or correct the address in the venues file
and run it again with --redo. tests/test_venue_coordinates.py fails while a venue has no coordinates or
one lies outside its region (docs/data/region_bounds.json).
"""
import argparse
import json
import math
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'docs', 'data')
COORDINATES_FILE = os.path.join(DATA_DIR, 'venue_coordinates.json')
BOUNDS_FILE = os.path.join(DATA_DIR, 'region_bounds.json')
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'ArtBasil-geocoder/1.0 (+https://artbasil.info)'
DELAY_SECONDS = 1.1                 # Nominatim's policy: at most one request a second
HOUSE_RANK = 30                     # Nominatim place_rank of a building or an address point; lower is a street or an area
REFINE_RADIUS_KM = 1.5              # a venue-name match is trusted when it is this close to the street match
# A suite, unit, floor or room that the geocoder doesn't know: "Suite 444", "#300", "3rd Floor", "Ste. 5"
_UNIT_RE = re.compile(r',?\s*(?:#\s*\w+|(?:suite|ste\.?|unit|room|rm\.?|floor|fl\.?|studio)\s*\w+|\d+(?:st|nd|rd|th)\s+floor)\b', re.I)


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_coordinates(data):
    with open(COORDINATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write('\n')


def addresses_of(value):
    """The street addresses a venues file holds for one venue: a string, or a list of strings or
    {"label", "address"} objects (the same shapes docs/venueAddresses.js accepts). Blank ones are skipped."""
    items = [value] if isinstance(value, str) else (value if isinstance(value, list) else [])
    found = []
    for item in items:
        address = item if isinstance(item, str) else (item.get('address') if isinstance(item, dict) else None)
        if isinstance(address, str) and address.strip():
            found.append(address.strip())
    return found


_ABBREVIATIONS = {'St': 'Street', 'Ave': 'Avenue', 'Blvd': 'Boulevard', 'Rd': 'Road', 'Dr': 'Drive', 'Pl': 'Place',
                  'Ct': 'Court', 'Hwy': 'Highway', 'Ln': 'Lane', 'Pkwy': 'Parkway', 'Sq': 'Square',
                  'W': 'West', 'E': 'East', 'N': 'North', 'S': 'South'}
_ABBREVIATION_RE = re.compile(r'(?<![\w-])(' + '|'.join(_ABBREVIATIONS) + r')\.?(?![\w\'-])')
_FRENCH_SUFFIX = {'W': 'Ouest', 'E': 'Est', 'West': 'Ouest', 'East': 'Est'}
_FRENCH_STREET_RE = re.compile(r'^(?P<num>[\w-]+) (?P<name>.+?) (?P<kind>St|Street|Blvd|Ave|Avenue)\.?(?: (?P<dir>[WE]|West|East))?(?P<rest>,.*)$')
_FRENCH_KIND = {'St': 'Rue', 'Street': 'Rue', 'Blvd': 'Boulevard', 'Ave': 'Avenue', 'Avenue': 'Avenue'}
_TURKISH_NUMBER_RE = re.compile(r'\bNo:\s*(\d+)[^\s,]*')
_POSTAL_RE = re.compile(r',?\s*\b(?:\d{5}|[A-Z]\d[A-Z] ?\d[A-Z]\d)\b')


def expand_abbreviations(address):
    """"5130 W Edgewood Pl, ..." -> "5130 West Edgewood Place, ...": OpenStreetMap spells street types out.
    Only the street part (before the first comma) is changed."""
    street, sep, rest = address.partition(',')
    return _ABBREVIATION_RE.sub(lambda m: _ABBREVIATIONS[m.group(1)], street) + sep + rest


def french_street(address):
    """"4001 Berri St, Montreal" -> "4001 Rue Berri, Montreal"; "1400 De Maisonneuve Blvd W" -> "1400 Boulevard De
    Maisonneuve Ouest". Montreal's streets are named in French in OpenStreetMap. None if it doesn't fit."""
    m = _FRENCH_STREET_RE.match(address)
    if not m:
        return None
    suffix = f" {_FRENCH_SUFFIX[m.group('dir')]}" if m.group('dir') else ''
    return f"{m.group('num')} {_FRENCH_KIND[m.group('kind')]} {m.group('name')}{suffix}{m.group('rest')}"


def query_variants(address, region=None):
    """The address as written, then ever plainer: without a suite or floor (which the geocoder can't place),
    with street types spelled out, in French (Montreal), without a leading place name ("Mithun Lounge, 585
    Howard..."), and in the Turkish form without "No:" and the postal code. The building, not the suite,
    is what gets looked up, so the last variants are shared by every suite in it."""
    stripped = _UNIT_RE.sub('', address).strip(' ,')
    variants = [address, stripped]
    expanded = expand_abbreviations(stripped)
    variants.append(expanded)
    # OpenStreetMap often has "5130 Edgewood Place" where the address says "5130 W Edgewood Pl"
    no_direction = re.sub(r'^(\d+[\w-]*) [NSEW] ', r'\1 ', stripped)
    if no_direction != stripped:
        variants += [no_direction, expand_abbreviations(no_direction)]
    if region == 'mtl':
        french = french_street(stripped)
        if french:
            variants += [french, _POSTAL_RE.sub('', french)]
    parts = [p.strip() for p in stripped.split(',')]
    for i, part in enumerate(parts[1:-1], 1):               # a leading place name before the street number
        if re.match(r'^\d{1,4}\b\S*\s+\D', part) and not re.match(r'^\d', parts[0]):     # "585 Howard Street", not "34430 Beyoğlu"
            variants.append(', '.join(parts[i:]))
            break
    if region == 'ist' or _TURKISH_NUMBER_RE.search(stripped):
        turkish = _TURKISH_NUMBER_RE.sub(r'\1', stripped)
        variants += [turkish, _POSTAL_RE.sub('', turkish)]
        short = [p for p in turkish.split(',') if p.strip()]
        if len(short) > 3:                                    # street, neighbourhood, district, city: drop the neighbourhood
            variants.append(', '.join([short[0]] + short[-2:]))
    seen, unique = set(), []
    for v in variants:
        v = re.sub(r'\s+', ' ', v).strip(' ,')
        if v and v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def building_key(address):
    """What a lookup is shared by: the address without its suite, so a building's tenants are asked once."""
    return _UNIT_RE.sub('', address).strip(' ,')


def distance_km(a, b):
    """Straight-line distance between two {'lat', 'lng'} points."""
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    d_lat, d_lng = lat2 - lat1, math.radians(b['lng'] - a['lng'])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def in_bounds(lat, lng, bounds):
    return bounds['lat'][0] <= lat <= bounds['lat'][1] and bounds['lng'][0] <= lng <= bounds['lng'][1]


def entry_from(result):
    """A Nominatim result -> a coordinates entry (flagged approx if it matched less than a building)."""
    entry = {'lat': round(float(result['lat']), 6), 'lng': round(float(result['lon']), 6)}
    if int(result.get('place_rank') or 0) < HOUSE_RANK:
        entry['approx'] = True
    return entry


def search(address, bounds, session=requests):
    """Ask Nominatim for one address, only inside the region's bounding box. Returns the first result or None."""
    left, right = bounds['lng']
    bottom, top = bounds['lat']
    response = session.get(NOMINATIM_URL, params={'q': address, 'format': 'jsonv2', 'limit': 1,
                                                  'viewbox': f'{left},{top},{right},{bottom}', 'bounded': 1},
                           headers={'User-Agent': USER_AGENT}, timeout=30)
    if response.status_code in (403, 429):
        raise RuntimeError(f"Nominatim refused the request ({response.status_code}); stop and try later")
    response.raise_for_status()
    results = response.json()
    return results[0] if results else None


def city_of(address):
    """The city part of "..., Oakland, CA 94607" or "..., Istanbul, Türkiye" (the part before the last)."""
    parts = [p.strip() for p in address.split(',')]
    return parts[-2] if len(parts) >= 2 else parts[0]


def geocode(address, bounds, session=requests, pause=time.sleep, region=None, venue=None):
    """Coordinates for one address (its variants tried in turn), or None. A match on only the street is
    sharpened by searching for the venue by name, trusted if it lands within REFINE_RADIUS_KM of the street
    match; an address nothing finds is tried as "venue, city" and flagged approx."""
    best = None
    for n, variant in enumerate(query_variants(address, region)):
        if n:
            pause(DELAY_SECONDS)
        result = search(variant, bounds, session)
        if result:
            entry = entry_from(result)
            if in_bounds(entry['lat'], entry['lng'], bounds):
                best = entry
                break
    if venue and (best is None or best.get('approx')):
        # The name alone first (OpenStreetMap often knows the venue under another spelling, and the search
        # is already limited to the region), then with the city
        for query in (venue, f'{venue}, {city_of(address)}'):
            pause(DELAY_SECONDS)
            result = search(query, bounds, session)
            if not result:
                continue
            named = entry_from(result)
            if not in_bounds(named['lat'], named['lng'], bounds):
                continue
            if best is None:
                named['approx'] = True                         # nothing confirms it, so it is still worth a look
                return named
            if not named.get('approx') and distance_km(best, named) <= REFINE_RADIUS_KM:
                return named
    return best


def missing_addresses(venues, coordinates_for_region, only_venue=None, redo=None):
    """[(venue, index, address)] still to look up for one region."""
    todo = []
    for venue, value in venues.items():
        if only_venue and venue != only_venue:
            continue
        existing = coordinates_for_region.get(venue) or []
        for index, address in enumerate(addresses_of(value)):
            entry = existing[index] if index < len(existing) else None
            if entry is None or (venue == redo and not entry.get('manual')):
                todo.append((venue, index, address))
    return todo


def run(regions=None, redo=None, dry_run=False, session=requests, pause=time.sleep):
    bounds_by_region = load_json(BOUNDS_FILE, {})
    coordinates = load_json(COORDINATES_FILE, {})
    cache = {}                       # address -> entry, so a shared address is asked once
    not_found, rough = [], []
    for region in sorted(bounds_by_region):
        if regions and region not in regions:
            continue
        venues = load_json(os.path.join(DATA_DIR, f'{region}_venues.json'), {})
        mine = coordinates.setdefault(region, {})
        todo = missing_addresses(venues, mine, redo=redo)
        print(f'{region}: {len(todo)} address(es) to look up')
        for venue, index, address in todo:
            if dry_run:
                print(f'  would look up {venue}: {address}')
                continue
            key = building_key(address)
            if key not in cache:
                try:
                    cache[key] = geocode(address, bounds_by_region[region], session, pause, region, venue)
                except requests.RequestException as e:
                    print(f'  ! {venue}: {e}; skipped')
                    continue
                pause(DELAY_SECONDS)
            entry = cache.get(key)
            if entry is None:
                not_found.append((region, venue, address))
                continue
            slots = mine.setdefault(venue, [])
            while len(slots) <= index:
                slots.append(None)
            slots[index] = dict(entry)
            if entry.get('approx'):
                rough.append((region, venue, address))
            save_coordinates(coordinates)
        # venues in the file's order, and nothing left for a venue that no longer exists
        ordered = {v: mine[v] for v in venues if v in mine}
        coordinates[region] = ordered
        if not dry_run:
            save_coordinates(coordinates)
    if not dry_run:
        report(not_found, rough)
    return not_found, rough


def report(not_found, rough):
    for title, rows in (('NOT FOUND (no entry written; fix the address or add coordinates by hand)', not_found),
                        ('MATCHED ONLY ROUGHLY (street or area; check on a map, then set "manual": true)', rough)):
        if rows:
            print(f'\n{title}')
            for region, venue, address in rows:
                print(f'  [{region}] {venue}: {address}')
    if not (not_found or rough):
        print('\nEvery address was matched to a building.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--region', action='append', help='only this region (repeatable)')
    parser.add_argument('--redo', metavar='VENUE', help='look this venue up again (a "manual" entry is kept)')
    parser.add_argument('--dry-run', action='store_true', help='list what would be looked up and ask nothing')
    args = parser.parse_args(argv)
    try:
        run(args.region, args.redo, args.dry_run)
    except RuntimeError as e:
        print(f'\n{e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
