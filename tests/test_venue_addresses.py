# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from submissions import venue_addresses

HART = {'label': 'Hart House', 'address': '7 Hart House Circle, Toronto, ON'}
KINGS = {'label': "King's College Circle", 'address': "15 King's College Circle, Toronto, ON"}


class VenueAddressesTest(unittest.TestCase):
    def test_a_plain_address_is_one_address(self):
        self.assertEqual(venue_addresses('1 A St, Toronto, ON'), ['1 A St, Toronto, ON'])

    def test_a_list_of_spaces_gives_each_address(self):
        self.assertEqual(venue_addresses([HART, KINGS]), [HART['address'], KINGS['address']])

    def test_odd_values_do_not_raise(self):
        self.assertEqual(venue_addresses(None), [])
        self.assertEqual(venue_addresses([]), [])
        self.assertEqual(venue_addresses([None, 3, {'label': 'x'}]), [None])

    def test_every_committed_venues_file_is_readable(self):
        # Mirrors the check in tests/venueAddresses.test.js, from the Python side
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
        for name in os.listdir(data_dir):
            if name.endswith('_venues.json'):
                with open(os.path.join(data_dir, name)) as f:
                    for venue, value in json.load(f).items():
                        self.assertTrue(all(venue_addresses(value)), f'{name}: {venue}')

    def test_every_stored_show_that_names_its_spaces_names_ones_the_venue_has(self):
        # An event's `locations` (WEBSITE-122) are labels of its venue's addresses; one the venue lacks would be ignored by the map
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
        for name in os.listdir(data_dir):
            if not name.endswith('_events.json'):
                continue
            with open(os.path.join(data_dir, name), encoding='utf-8') as f:
                events = json.load(f)
            with open(os.path.join(data_dir, name.replace('_events', '_venues')), encoding='utf-8') as f:
                venues = json.load(f)
            for venue, shows in events.items():
                labels = {a.get('label') for a in venues.get(venue, []) if isinstance(a, dict)}
                for show in shows.values():
                    for label in show.get('locations') or []:
                        self.assertIn(label, labels, f"{name}: {venue}: {show.get('name')}")


if __name__ == '__main__':
    unittest.main()
