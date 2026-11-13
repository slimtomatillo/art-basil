# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# A reception is not a show. It is stored, tagged 'reception', and the site hides it (docs/dataManager.js), so
# receptions can be listed later by flipping one switch. No network; the data file is a temporary one.
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config
import processing


def event(name, tags=None):
    return {'name': name, 'venue': 'Venue', 'description': None, 'tags': tags or ['exhibition', 'future', 'gallery'],
            'phase': 'future', 'dates': {'start': '2027-01-01', 'end': '2027-02-01'}, 'ongoing': False,
            'links': [{'link': 'https://x.example/', 'description': 'Event Page'}], 'last_updated': '2026-11-13 00:00:00'}


class IsReceptionTest(unittest.TestCase):
    def test_reception_announcements_match(self):
        for name in ('Art Opening Reception this Wednesday 2/29', 'RED ALL NIGHTmare on 18th Street – Opening Reception',
                     'Opening Reception Friday November 13, 7-10pm', 'Closing reception', 'Artist Reception',
                     'Members Reception', 'VIP reception for Show', 'Reception Friday 6-8pm', 'reception on Saturday'):
            self.assertTrue(processing.is_reception(name), name)

    def test_shows_do_not(self):
        for name in ('The Reception Room', 'Receptions', 'Reception', 'Opening: Landscapes', 'Art Opening – Katherine Johnstone',
                     'Open House', '', None, 'Perception Reception Studies'):
            self.assertFalse(processing.is_reception(name), name)


class ProcessEventTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'test_events.json')
        with open(self.path, 'w') as f:
            json.dump({}, f)
        self.saved = config.DB_FILES.get('sf')
        config.DB_FILES['sf'] = self.path           # the real sf_events.json must never be written by a test

    def tearDown(self):
        config.DB_FILES['sf'] = self.saved
        self.dir.cleanup()

    def stored(self):
        with open(self.path) as f:
            return json.load(f).get('Venue', {})

    def test_a_reception_is_stored_and_tagged(self):
        processing.process_event(event('Show – Opening Reception', ['event', 'future', 'gallery']), 'sf')
        [stored] = self.stored().values()
        self.assertEqual(stored['name'], 'Show – Opening Reception')
        self.assertIn('reception', stored['tags'])

    def test_a_show_is_not_tagged(self):
        processing.process_event(event('The Reception Room'), 'sf')
        [stored] = self.stored().values()
        self.assertNotIn('reception', stored['tags'])

    def test_the_tag_is_added_once_however_often_it_is_processed(self):
        for _ in range(2):
            processing.process_event(event('Opening Reception Friday', ['event', 'future']), 'sf')
        [stored] = self.stored().values()
        self.assertEqual(stored['tags'].count('reception'), 1)


if __name__ == '__main__':
    unittest.main()
