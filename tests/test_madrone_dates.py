# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Madrone Art Bar posts an exhibition without a date range now and then ("SF Night Moves & Light Canopy"). The
# scraper dates it from the day it was published, which gave it a start and no end, so it stayed "current" for
# good. It ran until the next exhibition began. No network; the clock is fixed.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import madrone_art_bar as madrone

NOW = dt.datetime(2026, 11, 13, 12, 0)


class FixedClock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.replace(tzinfo=tz)


def post(title, published, text):
    return {'title': {'rendered': title}, 'content': {'rendered': f'<p>{text}</p>'}, 'excerpt': {'rendered': ''},
            'date': f'{published}T10:00:00', 'link': f'https://madroneartbar.com/{title.lower().replace(" ", "-")}/'}


def run(posts):
    stored = []
    with mock.patch.object(madrone, 'fetch_exhibition_posts', return_value=posts), \
            mock.patch.object(madrone.dt, 'datetime', FixedClock), \
            mock.patch.object(madrone, 'process_event', lambda details, region: stored.append(details)):
        madrone.scrape_madrone_art_bar(env='prod')
    return {e['name']: e for e in stored}


DATED_1 = post('Artvent 2025', '2025-11-01', 'December 1, 2025, to January 30th, 2026')
DATED_2 = post('Summer Show', '2026-07-01', 'July 23rd to September 21st 2026')
UNDATED = post('Wall Installation', '2025-08-20', 'Main wall installation, photos by someone')


class UndatedExhibitionTest(unittest.TestCase):
    def test_an_exhibition_with_no_range_ran_until_the_next_one_began(self):
        found = run([UNDATED, DATED_1, DATED_2])
        show = found['Wall Installation']
        self.assertEqual(show['dates'], {'start': dt.date(2025, 8, 20), 'end': dt.date(2025, 11, 30)})
        self.assertEqual(show['phase'], 'past')

    def test_the_newest_one_with_no_range_is_still_on(self):
        found = run([post('Newest', '2026-10-01', 'A wall installation'), DATED_1])
        self.assertEqual(found['Newest']['dates'], {'start': dt.date(2026, 10, 1), 'end': None})
        self.assertEqual(found['Newest']['phase'], 'current')

    def test_dated_exhibitions_are_unchanged(self):
        found = run([UNDATED, DATED_1, DATED_2])
        self.assertEqual(found['Artvent 2025']['dates'], {'start': dt.date(2025, 12, 1), 'end': dt.date(2026, 1, 30)})
        self.assertEqual(found['Summer Show']['dates'], {'start': dt.date(2026, 7, 23), 'end': dt.date(2026, 9, 21)})

    def test_an_undated_post_does_not_end_at_the_start_of_an_earlier_one(self):
        found = run([post('Older', '2025-03-01', 'No dates'), UNDATED, DATED_1])
        self.assertEqual(found['Older']['dates']['end'], dt.date(2025, 8, 19))        # the next start, not Artvent's
        self.assertEqual(found['Wall Installation']['dates']['end'], dt.date(2025, 11, 30))


if __name__ == '__main__':
    unittest.main()
