# Run with the project's Python: python -m unittest discover -s tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import ica_san_jose as ica

BASE = 'https://www.icasanjose.org'


class TitleCountTest(unittest.TestCase):
    def test_a_show_whose_page_moved_from_upcoming_to_current_is_not_counted_twice(self):
        stored = {f'{BASE}/upcoming-exhibitions/queeramericanmemorials/': {'name': 'Queer American Memorials at the ICA'}}
        listings = [('current', {'name': 'Queer American Memorials at the ICA',
                                 'link': f'{BASE}/current-exhibitions/queeramericanmemorials/'})]
        self.assertEqual(ica.count_titles(stored, listings)['Queer American Memorials at the ICA'], 1)

    def test_the_same_title_on_two_different_pages_is_still_counted_twice(self):
        stored = {f'{BASE}/exhibitions/lift-off-2019/': {'name': 'Lift Off'}}
        listings = [('current', {'name': 'Lift Off', 'link': f'{BASE}/current-exhibitions/lift-off-2026/'})]
        self.assertEqual(ica.count_titles(stored, listings)['Lift Off'], 2)

    def test_a_year_suffix_on_a_stored_name_is_ignored_when_counting(self):
        stored = {f'{BASE}/exhibitions/lift-off-2019/': {'name': 'Lift Off (2019)'}}
        listings = [('current', {'name': 'Lift Off', 'link': f'{BASE}/current-exhibitions/lift-off-2026/'})]
        self.assertEqual(ica.count_titles(stored, listings)['Lift Off'], 2)


if __name__ == '__main__':
    unittest.main()
