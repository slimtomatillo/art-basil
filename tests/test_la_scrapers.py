# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import (eighteenth_street_arts_center as eighteenth, fowler_museum_at_ucla as fowler,
                         japanese_american_national_museum as janm, skirball_cultural_center as skirball,
                         vincent_price_art_museum as vpam, wende_museum as wende)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 4)


def run(module, func, html):
    """Run one scraper over a page of text blocks (one line each); returns {name: stored event}."""
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', lambda url: BeautifulSoup(f'<main>{html}</main>', 'html.parser')), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {e['name']: e for e in stored}


def blocks(*lines):
    return ''.join(f'<p>{line}</p>' for line in lines)


class FowlerTest(unittest.TestCase):
    PAGE = blocks('Uhengaparaoa, Taonga Tuku Iho', 'October 11, 2026 – May 16, 2027',
                  'Field Notes from Begumpura', 'by Rahee Punyashloka', 'August 9, 2026 – Summer 2027',
                  'Intersections: World Arts, Local Lives', 'Ongoing')

    def test_a_season_end_leaves_the_end_open_and_a_byline_is_not_the_title(self):
        events = run(fowler, 'scrape_fowler_museum_at_ucla', self.PAGE)
        self.assertEqual(sorted(events), ['Field Notes from Begumpura', 'Uhengaparaoa, Taonga Tuku Iho'])
        notes = events['Field Notes from Begumpura']
        self.assertEqual((notes['dates']['start'], notes['dates']['end']), (dt.date(2026, 8, 9), None))
        self.assertIn('free', notes['tags'])

    def test_a_full_range_is_read_as_dates(self):
        show = run(fowler, 'scrape_fowler_museum_at_ucla', self.PAGE)['Uhengaparaoa, Taonga Tuku Iho']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (dt.date(2026, 10, 11), dt.date(2027, 5, 16)))


class WendeTest(unittest.TestCase):
    def test_month_ranges_run_to_the_end_of_the_last_month(self):
        self.assertEqual(wende._month_range('Nov 2026-Jan 2027'), (dt.date(2026, 11, 1), dt.date(2027, 1, 31)))
        self.assertEqual(wende._month_range('Sep 2026–Feb 2028'), (dt.date(2026, 9, 1), dt.date(2028, 2, 29)))
        self.assertEqual(wende._month_range('Some title'), (None, None))

    def test_titles_notices_and_the_free_tag(self):
        page = blocks('CURRENT', 'Between Two Empires: Argentina in the Cold War', 'Sep 2026-Jan 2027',
                      'Bumdog Torres', 'THIS STRUCTURE WILL BE REMOVED WITHIN THE NEXT 48 HOURS', 'Nov 2026-Jan 2027')
        events = run(wende, 'scrape_wende_museum', page)
        self.assertEqual(sorted(events), ['Between Two Empires: Argentina in the Cold War', 'Bumdog Torres'])
        self.assertTrue(all('free' in e['tags'] for e in events.values()))


class SkirballTest(unittest.TestCase):
    def test_on_view_through_gives_an_end_date_only_and_ongoing_is_skipped(self):
        page = blocks('On View Now', 'Common Ground', 'On view through January 2, 2028',
                      'Visions and Values', 'Ongoing')
        show = run(skirball, 'scrape_skirball_cultural_center', page)['Common Ground']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (None, dt.date(2028, 1, 2)))
        self.assertNotIn('free', show['tags'])


class VincentPriceTest(unittest.TestCase):
    def test_the_archive_after_the_current_section_is_not_read(self):
        page = blocks('Exhibitions', 'Past Exhibitions',            # the menu link above the list
                      'CURRENT', 'The Buddhist Bug', 'September 26, 2026 – May 22, 2027',
                      'UPCOMING EXHIBITIONS', 'Almendárez', 'November 21, 2026 – May 22, 2027',
                      'PAST EXHIBITIONS', 'Old Show With A Live Looking Date', 'October 1, 2026 – December 31, 2026')
        self.assertEqual(sorted(run(vpam, 'scrape_vincent_price_art_museum', page)), ['Almendárez', 'The Buddhist Bug'])


class EighteenthStreetTest(unittest.TestCase):
    def test_ranges_are_exhibitions_and_an_evening_is_an_event(self):
        page = blocks('ON VIEW', 'Momo Nagano: Archeology of Motherhood', 'June 1, 2026', '-', 'June 1, 2027',
                      'UPCOMING EXHIBITIONS', 'Sage Ni’Ja Whitson: Revival', 'November 8, 2026 @ 2:00 pm', '-', '5:00 pm')
        events = run(eighteenth, 'scrape_eighteenth_street_arts_center', page)
        self.assertIn('exhibition', events['Momo Nagano: Archeology of Motherhood']['tags'])
        evening = events['Sage Ni’Ja Whitson: Revival']
        self.assertIn('event', evening['tags'])
        self.assertEqual(evening['dates'], {'start': dt.date(2026, 11, 8), 'end': dt.date(2026, 11, 8)})


class JanmTest(unittest.TestCase):
    def test_only_upcoming_and_special_entries_with_dates_are_read(self):
        page = blocks('Upcoming Exhibition', 'Jan 23 - Aug 29, 2027', 'Pictures of Belonging',
                      'Upcoming Exhibition', 'Ongoing', 'In the Future We Call Now',
                      'Traveling Display', 'Jul 15 - Dec 25, 2026', 'A Show Elsewhere')
        events = run(janm, 'scrape_japanese_american_national_museum', page)
        self.assertEqual(list(events), ['Pictures of Belonging'])
        self.assertEqual(events['Pictures of Belonging']['phase'], 'future')


if __name__ == '__main__':
    unittest.main()
