# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# SFMOMA's date labels. The 2026 SECA Art Award's card reads "December 12, 2026-May 30, 2027Community Opening:
# Dec 10, 6 p.m. Public Preview Day: Dec 11" (the opening runs on after the range with no space), which the
# parser gave up on, so the show was stored with no dates. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import sfmoma

CARD = ('<a class="exhibitionsgrid-wrapper-grid-item" href="https://www.sfmoma.org/exhibition/{slug}/">'
        '<div class="exhibitionsgrid-wrapper-grid-item-text-title">{title}</div>'
        '<div class="exhibitionsgrid-wrapper-grid-item-text-date">{date}</div>'
        '<img class="exhibitionsgrid-wrapper-grid-item-image" src="https://img.example/{slug}.jpg"></a>')


def run_scraper(cards):
    """cards: [(title, date label)], all in the upcoming section. Returns {title: stored event}."""
    html = ('<div id="item--exhibitions-current"></div><div id="item--exhibitions-upcoming">'
            + ''.join(CARD.format(slug=f'show-{i}', title=t, date=d) for i, (t, d) in enumerate(cards))
            + '</div><div id="item--exhibitions-past"></div>')
    stored = []
    with mock.patch.object(sfmoma, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(html, 'html.parser')), \
            mock.patch.object(sfmoma, 'process_event', lambda details, region: stored.append(details)):
        sfmoma.scrape_sfmoma(env='prod')
    return {e['name']: e['dates'] for e in stored}


class SfmomaDatesTest(unittest.TestCase):
    def test_a_range_followed_by_opening_events_keeps_its_dates(self):
        found = run_scraper([('SECA', 'December 12, 2026–May 30, 2027Community Opening: Dec 10, 6 p.m. Public Preview Day: Dec 11')])
        self.assertEqual(found['SECA'], {'start': dt.date(2026, 12, 12), 'end': dt.date(2027, 5, 30)})

    def test_the_same_with_a_space_or_only_a_preview_day(self):
        found = run_scraper([('A', 'December 12, 2026–May 30, 2027 Community Opening: Dec 10, 6 p.m.'),
                             ('B', 'December 12, 2026–May 30, 2027 Public Preview Day: Dec 11')])
        expected = {'start': dt.date(2026, 12, 12), 'end': dt.date(2027, 5, 30)}
        self.assertEqual((found['A'], found['B']), (expected, expected))

    def test_other_labels_are_unchanged(self):
        found = run_scraper([('Opens', 'Opening November 21, 2026'), ('Range', 'November 5, 2026–January 3, 2027'),
                             ('Season', 'Fall 2027')])
        self.assertEqual(found['Opens'], {'start': dt.date(2026, 11, 21), 'end': None})
        self.assertEqual(found['Range'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2027, 1, 3)})
        self.assertEqual(found['Season'], {'start': None, 'end': None})        # a season is not a date: "Dates TBA"


if __name__ == '__main__':
    unittest.main()
