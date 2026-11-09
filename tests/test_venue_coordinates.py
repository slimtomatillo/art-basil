# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# WEBSITE-58: every venue address has coordinates in docs/data/venue_coordinates.json, inside its region
# (docs/data/region_bounds.json), and geocode_venues.py (the script that fills the file) behaves. The
# script tests use a temporary data folder and a fake geocoder; no network, and the real data is never written.
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import geocode_venues as g

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
BOUNDS = {'lat': [37.0, 38.0], 'lng': [-123.0, -122.0]}


def load(name):
    with open(os.path.join(DATA_DIR, name), encoding='utf-8') as f:
        return json.load(f)


class CommittedCoordinatesTest(unittest.TestCase):
    """The check that fails when a venue is added without coordinates (run `python geocode_venues.py`)."""

    def test_every_address_of_every_venue_has_coordinates_inside_its_region(self):
        bounds, coordinates = load('region_bounds.json'), load('venue_coordinates.json')
        problems = []
        for region, box in bounds.items():
            venues = load(f'{region}_venues.json')
            have = coordinates.get(region, {})
            for venue, value in venues.items():
                addresses = g.addresses_of(value)
                entries = have.get(venue) or []
                if len(entries) != len(addresses) or not all(entries):
                    problems.append(f'{region}: {venue} has {len([e for e in entries if e])} of {len(addresses)} coordinates')
                    continue
                for address, entry in zip(addresses, entries):
                    lat, lng = entry.get('lat'), entry.get('lng')
                    if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float)) and g.in_bounds(lat, lng, box)):
                        problems.append(f'{region}: {venue} ({address}) is outside the region: {lat}, {lng}')
            for venue in have:
                if venue not in venues:
                    problems.append(f'{region}: coordinates for {venue}, which is not in {region}_venues.json')
        self.assertEqual(problems, [], '\n' + '\n'.join(problems) + '\nRun: python geocode_venues.py')

    def test_every_region_with_venues_has_bounds(self):
        bounds = load('region_bounds.json')
        for name in os.listdir(DATA_DIR):
            if name.endswith('_venues.json'):
                self.assertIn(name.split('_')[0], bounds, f'add {name.split("_")[0]} to docs/data/region_bounds.json')


class HelpersTest(unittest.TestCase):
    def test_addresses_of_accepts_every_shape_the_front_end_does(self):
        self.assertEqual(g.addresses_of(' 1 A St, Oakland, CA '), ['1 A St, Oakland, CA'])
        self.assertEqual(g.addresses_of(['1 A St', {'label': 'B', 'address': '2 B St'}]), ['1 A St', '2 B St'])
        self.assertEqual(g.addresses_of([{'label': 'x'}, None, 3, '  ', {'address': ''}]), [])
        self.assertEqual(g.addresses_of(None), [])

    def test_a_suite_or_floor_is_dropped_in_a_second_variant_only(self):
        self.assertEqual(g.query_variants('372 Sainte-Catherine St W, Suite 444, Montreal, QC')[:2],
                         ['372 Sainte-Catherine St W, Suite 444, Montreal, QC', '372 Sainte-Catherine St W, Montreal, QC'])
        self.assertEqual(g.query_variants('585 Howard Street #300, San Francisco, CA')[:2],
                         ['585 Howard Street #300, San Francisco, CA', '585 Howard Street, San Francisco, CA'])
        self.assertEqual(g.query_variants('1 A St, 3rd Floor, Oakland, CA')[1], '1 A St, Oakland, CA')
        self.assertEqual(g.query_variants('1380 Sherbrooke St W, Montreal, QC')[0], '1380 Sherbrooke St W, Montreal, QC')

    def test_street_types_are_spelled_out_but_names_like_st_hubert_are_not(self):
        self.assertEqual(g.expand_abbreviations('5130 W Edgewood Pl, Los Angeles, CA'), '5130 West Edgewood Place, Los Angeles, CA')
        self.assertEqual(g.expand_abbreviations('944 Simmonds Rd, Sausalito, CA'), '944 Simmonds Road, Sausalito, CA')
        self.assertEqual(g.expand_abbreviations('5826 St-Hubert St, Montreal, QC'), '5826 St-Hubert Street, Montreal, QC')
        self.assertEqual(g.expand_abbreviations('1 A St, Oakland, CA'), '1 A Street, Oakland, CA')           # only the street part
        self.assertEqual(g.expand_abbreviations('1 Main St, St Paul, MN'), '1 Main Street, St Paul, MN')

    def test_a_directional_letter_after_the_number_is_tried_without_it(self):
        variants = g.query_variants('5130 W Edgewood Pl, Los Angeles, CA 90019', 'la')
        self.assertIn('5130 Edgewood Pl, Los Angeles, CA 90019', variants)
        self.assertIn('5130 Edgewood Place, Los Angeles, CA 90019', variants)

    def test_montreal_streets_get_a_french_variant_only_for_montreal(self):
        self.assertEqual(g.french_street('4001 Berri St, Montreal, QC H2L 4H2'), '4001 Rue Berri, Montreal, QC H2L 4H2')
        self.assertEqual(g.french_street('1400 De Maisonneuve Blvd W, Montreal, QC'), '1400 Boulevard De Maisonneuve Ouest, Montreal, QC')
        self.assertIsNone(g.french_street('Pier 56, Seattle'))
        self.assertIn('4001 Rue Berri, Montreal, QC H2L 4H2', g.query_variants('4001 Berri St, Montreal, QC H2L 4H2', 'mtl'))
        self.assertNotIn('4001 Rue Berri, Montreal, QC H2L 4H2', g.query_variants('4001 Berri St, Montreal, QC H2L 4H2', 'sf'))

    def test_a_leading_place_name_is_dropped_but_a_postal_code_is_not_taken_for_a_street_number(self):
        self.assertIn('585 Howard Street, San Francisco, CA 94105',
                      g.query_variants('Mithun Lounge, 585 Howard Street #300, San Francisco, CA 94105', 'sf'))
        for variant in g.query_variants('Meşrutiyet Caddesi No:65, Tepebaşı, 34430 Beyoğlu, Istanbul, Türkiye', 'ist'):
            self.assertTrue(variant.startswith('Meşrutiyet'), variant)

    def test_turkish_numbers_lose_the_no_prefix(self):
        variants = g.query_variants('Meşrutiyet Caddesi No:65/2, Tepebaşı, 34430 Beyoğlu, Istanbul, Türkiye', 'ist')
        self.assertIn('Meşrutiyet Caddesi 65, Tepebaşı, 34430 Beyoğlu, Istanbul, Türkiye', variants)
        self.assertIn('Meşrutiyet Caddesi 65, Istanbul, Türkiye', variants)

    def test_tenants_of_one_building_share_a_lookup_and_distances_are_straight_line(self):
        self.assertEqual(g.building_key('372 Sainte-Catherine St W, Suite 444, Montreal, QC'),
                         g.building_key('372 Sainte-Catherine St W, Suite 502, Montreal, QC'))
        a, b = {'lat': 37.7749, 'lng': -122.4194}, {'lat': 37.8044, 'lng': -122.2712}      # San Francisco to Oakland
        self.assertAlmostEqual(g.distance_km(a, b), 13.4, delta=0.5)
        self.assertEqual(g.distance_km(a, a), 0)

    def test_a_match_less_exact_than_a_building_is_flagged_approx(self):
        self.assertEqual(g.entry_from({'lat': '37.1234567', 'lon': '-122.5', 'place_rank': 30}), {'lat': 37.123457, 'lng': -122.5})
        self.assertEqual(g.entry_from({'lat': '37.1', 'lon': '-122.5', 'place_rank': 26})['approx'], True)

    def test_missing_addresses_skips_done_and_manual_entries(self):
        venues = {'A': '1 A St', 'B': [{'label': 'x', 'address': '2 B St'}, {'label': 'y', 'address': '3 B St'}], 'C': '4 C St'}
        have = {'A': [{'lat': 37.5, 'lng': -122.5}], 'B': [{'lat': 37.6, 'lng': -122.6, 'manual': True}], 'C': [{'lat': 1, 'lng': 2}]}
        self.assertEqual(g.missing_addresses(venues, have), [('B', 1, '3 B St')])
        self.assertEqual(g.missing_addresses(venues, have, redo='A'), [('A', 0, '1 A St'), ('B', 1, '3 B St')])
        self.assertEqual([v for v, _, _ in g.missing_addresses(venues, have, redo='B')], ['B'])      # manual is kept


class FakeSession:
    def __init__(self, results=None, status=200):
        self.results, self.status, self.calls = results or {}, status, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params['q'])
        outer = self

        class Response:
            status_code = outer.status

            def raise_for_status(self):
                if outer.status >= 400:
                    raise requests.HTTPError(str(outer.status))

            def json(self):
                found = outer.results.get(params['q'])
                return [found] if found else []
        return Response()


HOUSE = {'lat': '37.5', 'lon': '-122.5', 'place_rank': 30}


class GeocodeTest(unittest.TestCase):
    def test_the_unit_free_variant_is_tried_when_the_first_finds_nothing(self):
        session = FakeSession({'1 A St, Oakland, CA': HOUSE})
        entry = g.geocode('1 A St, Suite 4, Oakland, CA', BOUNDS, session, pause=lambda s: None)
        self.assertEqual(entry, {'lat': 37.5, 'lng': -122.5})
        self.assertEqual(session.calls, ['1 A St, Suite 4, Oakland, CA', '1 A St, Oakland, CA'])

    def test_a_result_outside_the_region_is_not_accepted(self):
        far = {'lat': '48.8', 'lon': '2.3', 'place_rank': 30}
        self.assertIsNone(g.geocode('1 A St, Oakland, CA', BOUNDS, FakeSession({'1 A St, Oakland, CA': far}), pause=lambda s: None))

    def test_a_street_only_match_is_sharpened_by_the_venues_name_when_it_lands_close(self):
        street = {'lat': '37.500', 'lon': '-122.500', 'place_rank': 26}
        poi = {'lat': '37.502', 'lon': '-122.501', 'place_rank': 30}
        session = FakeSession({'1 A St, Oakland, CA': street, 'The Venue, Oakland': poi})
        entry = g.geocode('1 A St, Oakland, CA', BOUNDS, session, pause=lambda s: None, venue='The Venue')
        self.assertEqual(entry, {'lat': 37.502, 'lng': -122.501})                    # no "approx": it is the building

    def test_the_venues_name_alone_is_tried_before_name_and_city(self):
        street = {'lat': '37.500', 'lon': '-122.500', 'place_rank': 26}
        poi = {'lat': '37.501', 'lon': '-122.501', 'place_rank': 30}
        session = FakeSession({'1 A St, Oakland, CA': street, 'The Venue': poi})
        g.geocode('1 A St, Oakland, CA', BOUNDS, session, pause=lambda s: None, venue='The Venue')
        self.assertEqual(session.calls[-1], 'The Venue')                                # found, so no second name query

    def test_a_name_match_far_from_the_street_match_is_not_trusted(self):
        street = {'lat': '37.500', 'lon': '-122.500', 'place_rank': 26}
        elsewhere = {'lat': '37.900', 'lon': '-122.100', 'place_rank': 30}
        session = FakeSession({'1 A St, Oakland, CA': street, 'The Venue, Oakland': elsewhere})
        entry = g.geocode('1 A St, Oakland, CA', BOUNDS, session, pause=lambda s: None, venue='The Venue')
        self.assertEqual(entry, {'lat': 37.5, 'lng': -122.5, 'approx': True})

    def test_an_address_nothing_finds_falls_back_to_the_venue_name_and_is_flagged_approx(self):
        poi = {'lat': '37.5', 'lon': '-122.5', 'place_rank': 30}
        session = FakeSession({'The Venue, Oakland': poi})
        entry = g.geocode('9 Nowhere Rd, Oakland, CA', BOUNDS, session, pause=lambda s: None, venue='The Venue')
        self.assertEqual(entry, {'lat': 37.5, 'lng': -122.5, 'approx': True})
        self.assertEqual(g.city_of('1 A St, Oakland, CA 94607'), 'Oakland')

    def test_being_refused_stops_the_run(self):
        with self.assertRaises(RuntimeError):
            g.geocode('1 A St', BOUNDS, FakeSession(status=429), pause=lambda s: None)


class RunTest(unittest.TestCase):
    def test_a_run_fills_gaps_keeps_manual_entries_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            def write(name, data):
                with open(os.path.join(tmp, name), 'w') as f:
                    json.dump(data, f)
            write('region_bounds.json', {'sf': BOUNDS})
            write('sf_venues.json', {'Done': '1 A St', 'Manual': '2 B St', 'New': '3 C St', 'Rough': '4 D St', 'Lost': '5 E St',
                                     'Twin': '3 C St'})
            write('venue_coordinates.json', {'sf': {'Done': [{'lat': 37.1, 'lng': -122.1}],
                                                    'Manual': [{'lat': 37.2, 'lng': -122.2, 'manual': True}],
                                                    'Gone': [{'lat': 37.3, 'lng': -122.3}]}})
            session = FakeSession({'3 C St': HOUSE, '4 D St': {'lat': '37.6', 'lon': '-122.6', 'place_rank': 26}})
            with mock.patch.object(g, 'DATA_DIR', tmp), mock.patch.object(g, 'BOUNDS_FILE', os.path.join(tmp, 'region_bounds.json')), \
                    mock.patch.object(g, 'COORDINATES_FILE', os.path.join(tmp, 'venue_coordinates.json')):
                not_found, rough = g.run(session=session, pause=lambda s: None)
                with open(os.path.join(tmp, 'venue_coordinates.json')) as f:
                    saved = json.load(f)['sf']
        self.assertEqual(list(saved), ['Done', 'Manual', 'New', 'Rough', 'Twin'])      # the venues file's order; 'Gone' dropped
        self.assertEqual(saved['Done'], [{'lat': 37.1, 'lng': -122.1}])                # untouched
        self.assertEqual(saved['Manual'][0]['manual'], True)
        self.assertEqual(saved['New'], [{'lat': 37.5, 'lng': -122.5}])
        self.assertEqual(saved['Twin'], saved['New'])                                    # the shared address was asked once
        self.assertEqual(session.calls.count('3 C St'), 1)
        self.assertEqual(not_found, [('sf', 'Lost', '5 E St')])
        self.assertEqual(rough, [('sf', 'Rough', '4 D St')])
        self.assertTrue(saved['Rough'][0]['approx'])


if __name__ == '__main__':
    unittest.main()
