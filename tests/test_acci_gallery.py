# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Between shows ACCI's menu points "Current Exhibition" at its list of upcoming exhibitions. That page was
# stored as a show called "Upcoming Exhibitions" with the dates of the last one. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import acci_gallery

TODAY = dt.date(2026, 10, 20)


def home(name, href):
    return f'<ul><li>Current Exhibition<ul><li><a href="{href}">{name}</a></li></ul></li></ul>'


def run(name, href, page):
    pages = {acci_gallery.BASE_URL + '/': home(name, href), f'{acci_gallery.BASE_URL}/{href}': page}
    stored = []
    with mock.patch.object(acci_gallery, 'fetch_and_parse',
                           lambda url, headers=None: BeautifulSoup(pages[url], 'html.parser') if url in pages else None), \
            mock.patch.object(acci_gallery, 'region_today', lambda region: TODAY), \
            mock.patch.object(acci_gallery, 'process_event', lambda details, region: stored.append(details)):
        acci_gallery.scrape_acci_gallery(env='prod')
    return stored


SHOW_PAGE = '<html><body><h1>Masquerade: Art to Wear</h1><p>October 3 - November 8, 2026</p></body></html>'


class AcciTest(unittest.TestCase):
    def test_a_real_show_is_stored(self):
        stored = run('Masquerade: Art to Wear', 'masquerade.html', SHOW_PAGE)
        self.assertEqual([e['name'] for e in stored], ['Masquerade: Art to Wear'])
        self.assertEqual(stored[0]['dates'], {'start': dt.date(2026, 10, 3), 'end': dt.date(2026, 11, 8)})

    def test_the_list_of_upcoming_exhibitions_is_not_a_show(self):
        for name, href in (('Upcoming Exhibitions', 'upcoming-exhibition-list.html'),
                           ('Upcoming Exhibition', 'upcoming.html'), ('Next show', 'upcoming-exhibition-list.html')):
            with self.assertLogs(level='WARNING') as logs:
                stored = run(name, href, SHOW_PAGE)                 # the list page even carries a show's dates
            self.assertEqual(stored, [], name)
            self.assertIn('existing data kept', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
