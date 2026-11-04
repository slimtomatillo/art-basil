# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# find_unseen_events: current/upcoming events a working scraper no longer reports (a show that
# dropped off its listing, or sits on a page the scraper doesn't read). Temporary event files
# are swapped into config.DB_FILES; nothing real is read.
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import scraper_health
from config import DB_FILES

NOW = dt.datetime(2026, 11, 4, 12, 0, 0)


def stamp(days_ago):
    return (NOW - dt.timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')


def event(name, days_ago, phase='current', **extra):
    return {'name': name, 'phase': phase, 'last_updated': stamp(days_ago), **extra}


class UnseenEventsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        path = os.path.join(self.dir.name, 'test_events.json')
        patcher = mock.patch.dict(DB_FILES, {'test': path}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.path = path

    def write(self, db):
        with open(self.path, 'w') as f:
            json.dump(db, f)

    def unseen(self):
        return scraper_health.find_unseen_events(NOW)

    def test_an_old_event_at_a_venue_that_is_otherwise_refreshing_is_flagged(self):
        self.write({'LACMA': {'a': event('Fresh', 0), 'b': event('Metropolis II', 37), 'c': event('Upcoming ghost', 40, 'future')}})
        found = self.unseen()
        self.assertEqual([(u['name'], u['days'], u['phase']) for u in found],
                         [('Upcoming ghost', 40, 'future'), ('Metropolis II', 37, 'current')])

    def test_recent_past_manual_and_archive_events_are_not_flagged(self):
        self.write({'V': {'fresh': event('Fresh', 1), 'recent': event('Four days', 4), 'borderline': event('Three weeks', 21),
                          'past': event('Old past show', 300, 'past'),
                          'manual': event('By hand', 300, source='manual'), 'archive': event('Imported', 300, source='archive')}})
        self.assertEqual(self.unseen(), [])

    def test_a_venue_already_reported_stale_is_left_to_that_report(self):
        self.write({'Dead': {'a': event('Old', 60), 'b': event('Older', 90)}})
        self.assertEqual(self.unseen(), [])
        # ...so the same events would be flagged if the venue were not stale
        self.assertEqual(len(scraper_health.find_unseen_events(NOW, stale=[])), 2)

    def test_report_text_lists_them(self):
        unseen = [{'region': 'la', 'venue': 'LACMA', 'name': 'Metropolis II', 'days': 37, 'phase': 'current'}]
        text = scraper_health.render_markdown([], [], unseen)
        self.assertIn('not seen on the venue', text)
        self.assertIn('`la` **LACMA**: Metropolis II (current, last seen 37 days ago)', text)
        self.assertIn('All scrapers ran', scraper_health.render_markdown([], [], []))


if __name__ == '__main__':
    unittest.main()
