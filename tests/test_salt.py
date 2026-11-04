# Run with the project's Python: python -m unittest discover -s tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.ist import salt


class SaltTitleTest(unittest.TestCase):
    def test_the_exhibition_label_is_dropped_before_and_after_opening(self):
        self.assertEqual(salt.clean_title('Exhibition: No Admittance Except on Business'), 'No Admittance Except on Business')
        self.assertEqual(salt.clean_title('Upcoming Exhibition: No Admittance Except on Business'), 'No Admittance Except on Business')
        self.assertEqual(salt.clean_title('Upcoming   exhibition:  Some  Show'), 'Some Show')

    def test_other_titles_are_left_alone(self):
        self.assertEqual(salt.clean_title('Exhibitions of the Self'), 'Exhibitions of the Self')


if __name__ == '__main__':
    unittest.main()
