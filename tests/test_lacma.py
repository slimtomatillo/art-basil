# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# LACMA: the date line on its listing cards ("Jun 12–Dec 6, 2026 | BCAM, Level 3") and the
# separate "Ongoing" tab that lists its permanent installations. No network, no event data.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import lacma

D = dt.date


class ParseCardDatesTest(unittest.TestCase):
    def test_gallery_after_the_bar_is_not_part_of_the_date(self):
        self.assertEqual(lacma.parse_card_dates('Oct 18, 2026–Jan 24, 2027 | BCAM, Level 1'),
                         (D(2026, 10, 18), D(2027, 1, 24), False))

    def test_start_without_a_year_takes_the_end_year(self):
        self.assertEqual(lacma.parse_card_dates('Jun 12–Dec 6, 2026 | BCAM, Level 3'), (D(2026, 6, 12), D(2026, 12, 6), False))
        self.assertEqual(lacma.parse_card_dates('May 3–Nov 8, 2026'), (D(2026, 5, 3), D(2026, 11, 8), False))

    def test_a_start_later_in_the_year_than_the_end_began_the_year_before(self):
        self.assertEqual(lacma.parse_card_dates('Dec 21–Jan 3, 2027 | Resnick Pavilion'), (D(2026, 12, 21), D(2027, 1, 3), False))

    def test_ongoing_has_no_dates(self):
        self.assertEqual(lacma.parse_card_dates('Ongoing | Outdoor'), (None, None, True))
        self.assertEqual(lacma.parse_card_dates('Ongoing'), (None, None, True))

    def test_full_dates_and_junk(self):
        self.assertEqual(lacma.parse_card_dates('June 14, 2026–October 12, 2026'), (D(2026, 6, 14), D(2026, 10, 12), False))
        self.assertEqual(lacma.parse_card_dates(None), (None, None, False))


def card(title, dates):
    return (f'<article class="exhibition grid-item"><a href="/art/exhibition/{title.lower().replace(" ", "-")}"></a>'
            f'<header><h3>{title}</h3><p>{dates}</p></header></article>')


class ScrapeTest(unittest.TestCase):
    PAGES = {
        'https://www.lacma.org/currentexhibitions': card('Danse Macabre', 'Jun 12–Dec 6, 2026 | BCAM, Level 3'),
        'https://www.lacma.org/upcomingexhibitions': '',
        'https://www.lacma.org/pastexhibitions': '',
        'https://www.lacma.org/art/exhibitions/ongoing': card('Chris Burden: Metropolis II', 'Ongoing | BCAM, Level 1'),
    }

    def scrape(self, pages=None):
        pages = pages or self.PAGES
        stored = []
        with mock.patch.object(lacma, 'fetch_and_parse', side_effect=lambda u: BeautifulSoup(pages[u], 'html.parser') if u in pages else None), \
                mock.patch.object(lacma, 'process_event', side_effect=lambda d, r: stored.append(d)):
            lacma.scrape_lacma_exhibitions(env='prod')
        return {d['name']: d for d in stored}

    def test_current_show_keeps_both_dates(self):
        show = self.scrape()['Danse Macabre']
        self.assertEqual((show['phase'], show['dates']), ('current', {'start': D(2026, 6, 12), 'end': D(2026, 12, 6)}))
        self.assertFalse(show['ongoing'])

    def test_permanent_installations_come_from_the_ongoing_page(self):
        installation = self.scrape()['Chris Burden: Metropolis II']
        self.assertEqual(installation['phase'], 'current')
        self.assertTrue(installation['ongoing'])
        self.assertEqual(installation['dates'], {'start': None, 'end': None})

    def test_an_unreachable_ongoing_page_does_not_stop_the_rest(self):
        pages = {k: v for k, v in self.PAGES.items() if 'ongoing' not in k}
        self.assertEqual(list(self.scrape(pages)), ['Danse Macabre'])


if __name__ == '__main__':
    unittest.main()
