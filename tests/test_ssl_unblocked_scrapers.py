# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.ist import borusan_contemporary
from scrapers.tor import _common, image_centre

TODAY = dt.date(2026, 11, 4)


def run(module, func, html):
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(f'<main>{html}</main>', 'html.parser')), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {e['name']: e for e in stored}


def blocks(*lines):
    return ''.join(f'<p>{line}</p>' for line in lines)


class ImageCentreTest(unittest.TestCase):
    PAGE = (blocks('Current Exhibitions', 'Richard Avedon Immortal: Portraits of Aging, 1951–2004', 'September 9–December 5, 2026',
                   'South Gallery & North Gallery', 'Curator: Paul Roth')
            + '<a href="/exhibition/richard-avedon-immortal">Learn more</a>'
            + blocks('Upcoming', 'Donna Gottschalk: We Others', 'January 20–April 3, 2027', 'Main Gallery')
            + '<a href="/exhibition/donna-gottschalk-we-others">Learn more</a>')

    def test_current_and_upcoming_shows_are_free_museum_shows_linked_to_their_pages(self):
        events = run(image_centre, 'scrape_image_centre', self.PAGE)
        self.assertEqual(sorted(events), ['Donna Gottschalk: We Others', 'Richard Avedon Immortal: Portraits of Aging, 1951–2004'])
        avedon = events['Richard Avedon Immortal: Portraits of Aging, 1951–2004']
        self.assertEqual(avedon['dates'], {'start': dt.date(2026, 9, 9), 'end': dt.date(2026, 12, 5)})
        self.assertIn('free', avedon['tags'])
        self.assertIn({'link': 'https://www.theimagecentre.ca/exhibition/richard-avedon-immortal', 'description': 'Event Page'}, avedon['links'])
        self.assertEqual(events['Donna Gottschalk: We Others']['phase'], 'future')


class BorusanTest(unittest.TestCase):
    def test_day_first_english_ranges_with_the_title_above(self):
        page = blocks('Current Exhibitions', 'Haunted', '19 September 2026 - 15 August 2027', 'COLLECTION EXHIBITION', 'CURATOR: DR. KUMRU EREN',
                      'Time Space Geometry', '19 September 2026 - 15 August 2027', 'TEMPORARY EXHIBITION')
        events = run(borusan_contemporary, 'scrape_borusan_contemporary', page)
        self.assertEqual(sorted(events), ['Haunted', 'Time Space Geometry'])
        self.assertEqual(events['Haunted']['dates'], {'start': dt.date(2026, 9, 19), 'end': dt.date(2027, 8, 15)})


if __name__ == '__main__':
    unittest.main()
