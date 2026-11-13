# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# check_venues.py: runs a few venues' scrapers against a temporary events file and lists what they found. No network.
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import check_venues
import config


class VenueNamesTest(unittest.TestCase):
    def test_names_may_be_separate_arguments_or_comma_separated(self):
        self.assertEqual(check_venues.venue_names(['Cooper Hewitt', 'The Jewish Museum']), ['Cooper Hewitt', 'The Jewish Museum'])
        self.assertEqual(check_venues.venue_names(['Cooper Hewitt, The Jewish Museum ,', 'Pace Gallery']),
                         ['Cooper Hewitt', 'The Jewish Museum', 'Pace Gallery'])

    def test_a_proxied_venue_is_recognised(self):
        self.assertEqual(check_venues.proxied(['Cooper Hewitt', 'BAMPFA']), ['BAMPFA'])


class RunTest(unittest.TestCase):
    def test_the_regions_file_is_swapped_for_a_temporary_one_and_put_back(self):
        real = config.DB_FILES['nyc']
        seen = {}

        def fake_main(env, selected_regions, selected_venues, write_summary):
            seen['path'] = config.DB_FILES['nyc']
            seen['args'] = (env, selected_regions, selected_venues, write_summary)
            with open(config.DB_FILES['nyc'], 'w') as f:
                json.dump({'Cooper Hewitt': {'x': {'name': 'A show', 'phase': 'current', 'dates': {'start': None, 'end': '2027-02-15'},
                                                    'links': [{'link': 'u', 'description': 'Image'}], 'description': 'text'}}}, f)
            return []

        import main
        with mock.patch.object(main, 'main', side_effect=fake_main):
            failed, found = check_venues.run('nyc', ['Cooper Hewitt'])
        self.assertNotEqual(seen['path'], real)
        self.assertEqual(config.DB_FILES['nyc'], real)
        self.assertEqual(seen['args'], ('prod', ['nyc'], ['Cooper Hewitt'], False))
        self.assertEqual(failed, [])
        self.assertEqual([e['name'] for e in found['Cooper Hewitt']], ['A show'])

    def test_the_files_are_restored_even_when_a_scraper_run_blows_up(self):
        real = config.DB_FILES['nyc']
        import main
        with mock.patch.object(main, 'main', side_effect=RuntimeError('boom')), self.assertRaises(RuntimeError):
            check_venues.run('nyc', ['Cooper Hewitt'])
        self.assertEqual(config.DB_FILES['nyc'], real)


class ReportTest(unittest.TestCase):
    def test_each_venue_is_listed_and_a_venue_with_nothing_is_counted(self):
        found = {'A': [{'name': 'Show', 'phase': 'future', 'dates': {'start': '2027-01-01', 'end': None}, 'links': [], 'description': None}]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            empty = check_venues.report(['A', 'B'], found)
        text = out.getvalue()
        self.assertEqual(empty, 1)
        self.assertIn('A: 1 show', text)
        self.assertIn('B: 0 shows', text)
        self.assertIn('desc=no', text)
        self.assertIn('picture=no', text)


if __name__ == '__main__':
    unittest.main()
