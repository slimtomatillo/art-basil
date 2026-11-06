# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# image_audit.py reports which current and upcoming events have no picture of their own. Event
# files are temporary ones swapped into config.DB_FILES; nothing real is read or written.
import datetime as dt
import json
import os
import sys
import logging
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import image_audit
from config import DB_FILES, InfoFilter

TODAY = dt.date(2026, 11, 4)
PAGE = [{'link': 'https://g.example/s', 'description': 'Event Page'}]
PHOTO = PAGE + [{'link': 'https://g.example/p.jpg', 'description': 'Image'}]


def event(name, phase='current', links=PAGE, **extra):
    return {'name': name, 'phase': phase, 'links': links, **extra}


class ImageAuditTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        patcher = mock.patch.dict(DB_FILES, {'test': os.path.join(self.dir.name, 'test_events.json')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, db, logos=None):
        with open(DB_FILES['test'], 'w') as f:
            json.dump(db, f)
        if logos is not None:
            with open(os.path.join(self.dir.name, 'venue_images.json'), 'w') as f:
                json.dump(logos, f)

    def audit(self):
        return image_audit.collect(['test'])

    def test_events_are_counted_as_own_logo_or_none(self):
        self.write({
            'Has Logo': {'a': event('A'), 'b': event('B', links=PHOTO)},
            'No Logo': {'c': event('C', image_checked='2026-10-30')},
        }, logos={'Has Logo': 'https://g.example/logo.png'})
        audit = self.audit()
        self.assertEqual({k: audit[('test', 'Has Logo')][k] for k in ('total', 'own', 'logo', 'none')},
                         {'total': 2, 'own': 1, 'logo': 1, 'none': 0})
        self.assertEqual({k: audit[('test', 'No Logo')][k] for k in ('total', 'own', 'logo', 'none')},
                         {'total': 1, 'own': 0, 'logo': 0, 'none': 1})
        missing = audit[('test', 'No Logo')]['missing'][0]
        self.assertEqual((missing['name'], missing['state'], missing['checked'], missing['page']),
                         ('C', 'none', '2026-10-30', 'https://g.example/s'))

    def test_past_events_are_ignored_and_a_venue_with_only_past_events_is_left_out(self):
        self.write({'Old': {'a': event('A', phase='past')}, 'Mixed': {'b': event('B'), 'c': event('C', phase='past')}})
        audit = self.audit()
        self.assertNotIn(('test', 'Old'), audit)
        self.assertEqual(audit[('test', 'Mixed')]['total'], 1)

    def test_manual_events_are_counted_and_marked(self):
        self.write({'V': {'a': event('A', source='manual')}})
        self.assertEqual(self.audit()[('test', 'V')]['missing'][0]['source'], 'manual')

    def test_a_missing_or_broken_logo_file_means_no_logos(self):
        self.write({'V': {'a': event('A')}})
        self.assertEqual(self.audit()[('test', 'V')]['none'], 1)
        with open(os.path.join(self.dir.name, 'venue_images.json'), 'w') as f:
            f.write('not json')
        self.assertEqual(self.audit()[('test', 'V')]['none'], 1)

    def test_report_lists_the_worst_venues_first_with_links_and_check_dates(self):
        self.write({'Small': {'a': event('A')},
                    'Big': {'b': event('B'), 'c': event('C', image_checked='2026-11-01'), 'd': event('D', links=PHOTO)}},
                   logos={'Small': 'https://g.example/l.png'})
        text = image_audit.render_markdown(self.audit(), TODAY)
        self.assertIn('Current and upcoming events on 2026-11-04: **4**', text)
        self.assertIn('With their own picture: **1** (25%)', text)
        self.assertLess(text.index('| `test` | Big |'), text.index('| `test` | Small |'))
        self.assertIn('- [C](https://g.example/s): blank; page last checked 2026-11-01', text)
        self.assertIn('- [A](https://g.example/s): venue logo; page not checked yet', text)

    def test_report_without_the_event_list_is_just_the_table(self):
        self.write({'V': {'a': event('A')}})
        text = image_audit.render_markdown(self.audit(), TODAY, details=False)
        self.assertIn('| `test` | V |', text)
        self.assertNotIn('Events without a picture', text)

    def test_everything_covered(self):
        self.write({'V': {'a': event('A', links=PHOTO)}})
        self.assertIn('Every event has a picture of its own.', image_audit.render_markdown(self.audit(), TODAY))

    def test_write_report_saves_the_file_and_the_job_summary(self):
        self.write({'V': {'a': event('A')}})
        report = os.path.join(self.dir.name, 'IMAGE_AUDIT.md')
        summary = os.path.join(self.dir.name, 'summary.md')
        with mock.patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': summary}):
            t = image_audit.write_report(TODAY, ['test'], path=report)
        self.assertEqual(t, {'total': 1, 'own': 0, 'logo': 0, 'none': 1})
        with open(report) as f:
            self.assertIn('### Events without a picture of their own', f.read())
        with open(summary) as f:
            body = f.read()
        self.assertIn('| `test` | V |', body)
        self.assertNotIn('### Events without', body)

    def test_the_summary_line_gets_past_the_console_log_filter(self):
        # config.InfoFilter hides INFO lines without certain words; the audit line was silently dropped once
        self.write({'V': {'a': event('A')}})
        with self.assertLogs(level=logging.INFO) as logs:
            image_audit.write_report(TODAY, ['test'], path=os.path.join(self.dir.name, 'IMAGE_AUDIT.md'))
        record = next(r for r in logs.records if 'image audit' in r.getMessage().lower())
        self.assertTrue(InfoFilter().filter(record), record.getMessage())


if __name__ == '__main__':
    unittest.main()
