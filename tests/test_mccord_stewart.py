# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# McCord Stewart's "Expo 67" is announced for "Spring 2027". Its date line can't be parsed, so it was stored as
# a current show with no dates (listed as on now, since late October). A season that has not begun means the
# show is coming. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.mtl import mccord_stewart

TODAY = dt.date(2026, 11, 12)


class SeasonTest(unittest.TestCase):
    def test_a_season_that_has_not_begun_is_upcoming(self):
        for text in ('Spring 2027', 'spring 2027', ' Spring\xa02027 ', 'Summer 2027', 'Fall 2027', 'Autumn 2027', 'Winter 2026'):
            self.assertTrue(mccord_stewart.upcoming_season(text, TODAY), text)

    def test_a_season_that_has_begun_or_is_not_a_season_is_not(self):
        for text in ('Fall 2026', 'Winter 2025', 'Spring 2026', None, '', 'Until March 1, 2027', 'On-going', 'Spring', '2027',
                     'Spring 2027 and summer'):
            self.assertFalse(mccord_stewart.upcoming_season(text, TODAY), text)

    def test_a_season_is_not_given_a_date(self):
        self.assertEqual(mccord_stewart.parse_date_text('Spring 2027'), (None, None, False))


LISTING = '''<div class="event"><a href="https://mccord.example/en/exhibitions/{slug}/"><h1>{title}</h1>
<img src="https://mccord.example/{slug}.jpg"></a></div>'''
DETAIL = '<html><body><p class="date">{date}</p><meta name="description" content="About it"></body></html>'


def run_scraper(shows):
    """shows: [(slug, title, date text on its page)]. Returns {name: stored event}."""
    listing = '<main>' + ''.join(LISTING.format(slug=s, title=t) for s, t, _ in shows) + '</main>'
    pages = {mccord_stewart.LISTING_URL: listing,
             **{f'https://mccord.example/en/exhibitions/{s}/': DETAIL.format(date=d) for s, _, d in shows}}
    stored = []
    with mock.patch.object(mccord_stewart, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(pages[url], 'html.parser')), \
            mock.patch.object(mccord_stewart.time, 'sleep', lambda s: None), \
            mock.patch.object(mccord_stewart, 'process_event', lambda details, region: stored.append(details)):
        mccord_stewart.scrape_mccord_stewart_exhibitions(env='prod')
    return {e['name']: e for e in stored}


class ScraperTest(unittest.TestCase):
    def test_a_show_announced_for_a_season_is_a_future_show_with_no_dates(self):
        events = run_scraper([('expo-67', 'Expo 67', 'Spring 2099')])
        show = events['Expo 67']
        self.assertEqual(show['phase'], 'future')
        self.assertEqual(show['tags'], ['exhibition', 'future', 'museum'])
        self.assertEqual(show['dates'], {'start': None, 'end': None})       # no date is made up: the site says "Dates TBA"
        self.assertFalse(show['ongoing'])

    def test_a_season_that_has_begun_stays_a_current_show(self):
        self.assertEqual(run_scraper([('old', 'Old', 'Spring 2001')])['Old']['phase'], 'current')

    def test_dated_and_ongoing_shows_are_unchanged(self):
        events = run_scraper([('a', 'Until', 'Until March 1, 2099'), ('b', 'From', 'From March 1, 2099 to April 1, 2099'),
                              ('c', 'Always', 'On-going'), ('d', 'Undated', '')])
        self.assertEqual(events['Until']['phase'], 'current')
        self.assertEqual(events['From']['phase'], 'future')
        self.assertEqual((events['Always']['phase'], events['Always']['ongoing']), ('current', True))
        self.assertEqual(events['Undated']['phase'], 'current')             # nothing to go on: unchanged


if __name__ == '__main__':
    unittest.main()
