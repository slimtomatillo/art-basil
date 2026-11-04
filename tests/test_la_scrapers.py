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
                         vincent_price_art_museum as vpam, wende_museum as wende,
                         california_african_american_museum as caam, ica_la, molaa)
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


def run_pages(module, func, pages):
    """Like run(), for a scraper that reads several pages: pages maps each URL to its HTML."""
    stored = []

    def fetch(url, headers=None):
        return BeautifulSoup(f'<main>{pages[url]}</main>', 'html.parser') if url in pages else None

    with mock.patch.object(module, 'fetch_and_parse', fetch), \
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


class IcaLaTest(unittest.TestCase):
    PAGE = blocks('Current Exhibitions', 'Carl Cheng: Nature Never Loses', 'On view through February 28, 2027',
                  'Outdoor Projects', 'Zoe Walsh: Gathering', 'On view through February 28, 2027',
                  'Upcoming', 'Opening March 27, 2027', 'Teresa Baker: Somewhere Between', 'Opening November 07',
                  'Sming Sming Books', 'Find us on', 'Opening December 1', 'Not A Show')

    def test_current_shows_have_only_an_end_and_upcoming_ones_only_a_start(self):
        events = run(ica_la, 'scrape_ica_la', self.PAGE)
        self.assertEqual(sorted(events), ['Carl Cheng: Nature Never Loses', 'Sming Sming Books',
                                          'Teresa Baker: Somewhere Between', 'Zoe Walsh: Gathering'])
        self.assertEqual(events['Carl Cheng: Nature Never Loses']['dates'], {'start': None, 'end': dt.date(2027, 2, 28)})
        # No year given: the coming November 7
        self.assertEqual(events['Sming Sming Books']['dates']['start'], dt.date(2026, 11, 7))
        self.assertEqual(events['Teresa Baker: Somewhere Between']['phase'], 'future')


class MolaaTest(unittest.TestCase):
    PAGES = {
        'https://molaa.org/exhibitions/': '<a class="image-slide-anchor" href="/2026-red">x</a>'
                                          '<a class="image-slide-anchor" href="/2026-romero">x</a>'
                                          '<a class="image-slide-anchor" href="/molaa-collection-lab">x</a>'
                                          '<a class="image-slide-anchor">x</a>'
                                          '<a class="image-slide-anchor" href="/2025-old">x</a>',
        'https://molaa.org/2026-red': blocks('Donate', 'RED RED RED, Geometry of a Scar', 'ORGANIZED BY MIA ART COLLECTION',
                                             'Starting October 4, 2026 - February 21, 2027'),
        'https://molaa.org/2026-romero': blocks('Donate', 'Antonio Romero:', 'TROPICALIA [VOL2]', 'Exhibition Brochure',
                                                'Starting March 29, 2026'),
    }

    def test_current_slides_are_read_until_the_gap_and_titles_are_joined(self):
        events = run_pages(molaa, 'scrape_molaa', self.PAGES)
        self.assertEqual(sorted(events), ['Antonio Romero: TROPICALIA [VOL2]', 'RED RED RED, Geometry of a Scar'])
        self.assertEqual(events['RED RED RED, Geometry of a Scar']['dates'],
                         {'start': dt.date(2026, 10, 4), 'end': dt.date(2027, 2, 21)})
        self.assertIsNone(events['Antonio Romero: TROPICALIA [VOL2]']['dates']['end'])


class CaamTest(unittest.TestCase):
    @staticmethod
    def item(title, start, end, display=''):
        return {'title': title, 'contentUrl': 'https://caamuseum.org/x', 'content': {
            'start_date': start[0], 'start_year': start[1], 'end_date': end[0], 'end_year': end[1], 'display_date': display}}

    def test_ongoing_and_offsite_entries_are_skipped(self):
        feed = {'current': [self.item('Sinners', ('October 20', 2026), ('March 14', 2027)),
                            self.item('Public Sculpture', ('June 21', 2023), ('June 21', 2030), 'Ongoing'),
                            self.item('Elsewhere', ('October 20', 2026), ('February 27', 2027),
                                      'October 20, 2026 - February 27, 2027 at Art + Practice')],
                'upcoming': [self.item('Fred Wilson', ('November 17', 2026), ('April 4', 2027))]}
        stored = []
        response = mock.Mock(json=lambda: feed, raise_for_status=lambda: None)
        with mock.patch.object(caam.requests, 'get', return_value=response), \
                mock.patch.object(caam, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
            caam.scrape_california_african_american_museum(env='prod')
        events = {e['name']: e for e in stored}
        self.assertEqual(sorted(events), ['Fred Wilson', 'Sinners'])
        self.assertEqual(events['Fred Wilson']['phase'], 'future')


if __name__ == '__main__':
    unittest.main()
