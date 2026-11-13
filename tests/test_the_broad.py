# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The Broad's date ranges often give the year once ("Nov 18 - Apr 14, 2024"). The end's year was borrowed for
# the start, which put the start after the end. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import the_broad

URL = 'https://www.thebroad.org/art/special-exhibitions/example'


def details(date_text, title='A Show'):
    page = (f'<html><head><title>{title} | The Broad</title></head><body><div class="card-header-short__title">{title}</div>'
            f'<div class="card-header-short__date">{date_text}</div></body></html>')
    with mock.patch.object(the_broad, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(page, 'html.parser')):
        return the_broad.scrape_exhibition_details(URL)


class BroadDatesTest(unittest.TestCase):
    def range_of(self, text):
        found = details(text)
        dates = found.get('dates') or {'start': found.get('start_date'), 'end': found.get('end_date')}
        return dates['start'], dates['end']

    def test_a_show_that_opens_in_autumn_and_closes_in_spring_opened_the_year_before(self):
        self.assertEqual(self.range_of('Nov 18 - Apr 14, 2024'), (dt.date(2023, 11, 18), dt.date(2024, 4, 14)))
        self.assertEqual(self.range_of('November 16 - March 15, 2026'), (dt.date(2025, 11, 16), dt.date(2026, 3, 15)))

    def test_a_range_inside_one_year_keeps_that_year(self):
        self.assertEqual(self.range_of('May 10 - Sep 7, 2025'), (dt.date(2025, 5, 10), dt.date(2025, 9, 7)))

    def test_a_start_that_names_its_own_year_is_left_alone(self):
        self.assertEqual(self.range_of('November 18, 2023 - April 14, 2024'), (dt.date(2023, 11, 18), dt.date(2024, 4, 14)))

    def test_year_earlier(self):
        self.assertEqual(the_broad.year_earlier(dt.date(2024, 11, 18)), dt.date(2023, 11, 18))
        self.assertEqual(the_broad.year_earlier(dt.date(2024, 2, 29)), dt.date(2023, 2, 28))


class BroadNoTitleTest(unittest.TestCase):
    def test_a_page_with_no_title_is_logged_with_what_it_was(self):
        page = '<html><head><title>Something else</title></head><body><p>hello</p></body></html>'
        with mock.patch.object(the_broad, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(page, 'html.parser')):
            with self.assertLogs(level='WARNING') as logs:
                found = the_broad.scrape_exhibition_details(URL)
        self.assertIsNone(found['name'])
        self.assertIn("page title 'Something else'", '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
