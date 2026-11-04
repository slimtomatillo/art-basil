# Run with the project's Python: python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from date_parsing import parse_date_text

TODAY = dt.date(2026, 11, 4)


class FrenchDatesTest(unittest.TestCase):
    def test_day_first_ranges(self):
        self.assertEqual(parse_date_text('du 12 septembre au 20 décembre 2026', TODAY), (dt.date(2026, 9, 12), dt.date(2026, 12, 20)))
        self.assertEqual(parse_date_text('24 octobre au 28 novembre 2026', TODAY), (dt.date(2026, 10, 24), dt.date(2026, 11, 28)))
        self.assertEqual(parse_date_text('1er mai au 5 juin 2027', TODAY), (dt.date(2027, 5, 1), dt.date(2027, 6, 5)))
        self.assertEqual(parse_date_text('5 novembre au 12 décembre 2026', TODAY), (dt.date(2026, 11, 5), dt.date(2026, 12, 12)))

    def test_abbreviated_months(self):
        self.assertEqual(parse_date_text('2 oct au 28 nov 2026', TODAY), (dt.date(2026, 10, 2), dt.date(2026, 11, 28)))
        self.assertEqual(parse_date_text('12 sept. au 4 déc. 2026', TODAY), (dt.date(2026, 9, 12), dt.date(2026, 12, 4)))
        self.assertEqual(parse_date_text('20 au 28 nov 2026', TODAY), (dt.date(2026, 11, 20), dt.date(2026, 11, 28)))

    def test_until_and_lone_dates(self):
        self.assertEqual(parse_date_text("jusqu'au 15 mars 2027", TODAY), (None, dt.date(2027, 3, 15)))
        self.assertEqual(parse_date_text('8 août 2027', TODAY), (dt.date(2027, 8, 8), None))

    def test_english_dates_are_unchanged(self):
        self.assertEqual(parse_date_text('November 7 - December 19, 2026', TODAY), (dt.date(2026, 11, 7), dt.date(2026, 12, 19)))
        self.assertEqual(parse_date_text('Oct 3-24, 2026', TODAY), (dt.date(2026, 10, 3), dt.date(2026, 10, 24)))


if __name__ == '__main__':
    unittest.main()
