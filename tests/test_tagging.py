# Run with: python3 -m unittest discover -s tests
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import tagging


class FreeGalleryTest(unittest.TestCase):
    def tagged(self, tags):
        event = {'name': 'A show', 'description': '', 'venue': 'Somewhere', 'tags': list(tags)}
        tagging.add_content_tags(event)
        return event['tags']

    def test_gallery_is_free(self):
        self.assertIn('free', self.tagged(['exhibition', 'current', 'gallery']))

    def test_museum_is_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'current', 'museum']))

    def test_gallery_that_is_also_a_museum_is_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'gallery', 'museum']))

    def test_other_venues_are_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'current']))

    def test_free_is_added_once_and_existing_free_is_kept(self):
        tags = self.tagged(['gallery', 'free'])
        self.assertEqual(tags.count('free'), 1)


class RecordedAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.saved = tagging._free_venues
        tagging._free_venues = {'Free Museum'}

    def tearDown(self):
        tagging._free_venues = self.saved

    def tagged(self, venue, tags):
        event = {'name': 'A show', 'description': '', 'venue': venue, 'tags': list(tags)}
        tagging.add_content_tags(event)
        return event['tags']

    def test_museum_recorded_as_free_gets_the_tag(self):
        self.assertIn('free', self.tagged('Free Museum', ['exhibition', 'museum']))

    def test_museum_not_recorded_as_free_does_not(self):
        self.assertNotIn('free', self.tagged('Paid Museum', ['exhibition', 'museum']))

    def test_only_a_free_record_counts(self):
        tagging._free_venues = None
        free = tagging.free_venues()
        self.assertIn('Hammer Museum', free)
        self.assertNotIn('LACMA', free)          # recorded as paid
        self.assertNotIn('Madrone Art Bar', free)    # unverified


class AdmissionRecordTest(unittest.TestCase):
    def setUp(self):
        with open(tagging.ADMISSION_FILE, encoding='utf-8') as f:
            self.record = json.load(f)

    def test_every_entry_has_status_source_and_date(self):
        for region, venues in self.record.items():
            if region.startswith('_'):
                continue
            for venue, info in venues.items():
                self.assertIn(info.get('admission'), ('free', 'paid', 'unverified'), venue)
                self.assertTrue(info.get('source', '').startswith('http'), venue)
                self.assertRegex(info.get('checked', ''), r'^\d{4}-\d{2}-\d{2}$', venue)

    def test_every_museum_in_the_event_data_has_a_record(self):
        """A new museum scraper needs an entry in docs/data/venue_admission.json (see OPERATIONS.md)."""
        data = os.path.join(os.path.dirname(tagging.ADMISSION_FILE))
        missing = set()
        for region in ('sf', 'la', 'mtl', 'tor', 'ist'):
            with open(os.path.join(data, f'{region}_events.json'), encoding='utf-8') as f:
                events = json.load(f)
            known = self.record.get(region, {})
            for by_name in events.values():
                for event in by_name.values():
                    if 'museum' in (event.get('tags') or []) and event.get('venue') not in known:
                        missing.add((region, event.get('venue')))
        self.assertEqual(missing, set(), 'museums without an admission record')


if __name__ == '__main__':
    unittest.main()
