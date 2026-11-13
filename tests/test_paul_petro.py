# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Paul Petro's current page lists each show as title / artist / subtitle / dates / opening reception. The
# Christmas show has no artist line, so the line three above its dates was the previous show's reception, and
# it was stored as "Opening Reception Friday November 13, 7-10pm: 30th annual Christmas Spice - tree by ...".
# No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.tor import _common, paul_petro_contemporary_art as petro

TODAY = dt.date(2026, 11, 12)


def run(lines):
    html = '<main>' + ''.join(f'<p>{l}</p>' for l in lines) + '</main>'
    stored = []
    with mock.patch.object(petro, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(html, 'html.parser')), \
            mock.patch.object(petro, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        petro.scrape_paul_petro_contemporary_art(env='prod')
    return {e['name']: e['dates'] for e in stored}


PAGE = ['Paul Petro Contemporary Art', 'Current Programming', 'Wed-Sat 11-5pm',
        'Current Regional Programming', 'October 23, 2026 - January 31, 2027',
        'Here and There', 'Gary Evans', 'new paintings', 'November 13 - December 23, 2026',
        'Opening Reception Friday November 13, 7-10pm',
        '30th annual Christmas Spice', 'tree by Gary Evans', 'November 27 - December 23, 2026',
        'Opening Reception Friday November 27, 7-10pm']


class PaulPetroTest(unittest.TestCase):
    def test_a_show_with_no_artist_line_is_not_given_the_previous_shows_reception(self):
        found = run(PAGE)
        self.assertIn('30th annual Christmas Spice - tree by Gary Evans', found)
        self.assertEqual(found['30th annual Christmas Spice - tree by Gary Evans'],
                         {'start': dt.date(2026, 11, 27), 'end': dt.date(2026, 12, 23)})
        self.assertFalse([n for n in found if 'Opening Reception' in n])

    def test_a_show_with_title_artist_and_subtitle_is_named_as_before(self):
        found = run(PAGE)
        self.assertEqual(found['Here and There: Gary Evans - new paintings'],
                         {'start': dt.date(2026, 11, 13), 'end': dt.date(2026, 12, 23)})

    def test_the_regional_programming_block_is_still_skipped(self):
        found = run(PAGE)
        self.assertEqual(len(found), 2)


if __name__ == '__main__':
    unittest.main()
