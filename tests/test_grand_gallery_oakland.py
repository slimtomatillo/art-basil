# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The Grand Gallery Oakland home-page slider: shows are read from "Show Dates <range>", written with or
# without a colon; classes, past shows and unreadable slides are skipped. No network, no data.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import the_grand_gallery_oakland as grand

TODAY = dt.date(2026, 11, 6)
SLIDE = ('<div class="et_pb_slide"><h2 class="et_pb_slide_title"><a href="{url}">{title}</a></h2>'
         '<div class="et_pb_slide_content">{content}</div></div>')


def run(slides):
    stored = []
    page = BeautifulSoup('<div>' + ''.join(slides) + '</div>', 'html.parser') if slides is not None else None
    with mock.patch.object(grand, 'fetch_and_parse', return_value=page), \
            mock.patch.object(grand, 'region_today', return_value=TODAY), \
            mock.patch.object(grand, 'process_event', side_effect=lambda d, r: stored.append(d)):
        grand.scrape_the_grand_gallery_oakland(env='prod')
    return stored


def slide(title, content):
    return SLIDE.format(url=f'https://thegrandgalleryoakland.com/{title.lower()}/', title=title, content=content)


class GrandGalleryTest(unittest.TestCase):
    def test_show_dates_with_a_colon_are_read(self):
        stored = run([slide('Helvella', 'Show Dates: Nov 5th - Nov 29th Artist Reception Thursday Nov 12th, 6pm - 8pm '
                                        'Join us for the month of November.')])
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['name'], 'Helvella')
        self.assertEqual(stored[0]['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 11, 29)})
        self.assertEqual(stored[0]['phase'], 'current')

    def test_show_dates_without_a_colon_are_still_read(self):
        stored = run([slide('Tiny', 'Show Dates November 20th – 30th Artist Reception November 21st, Noon - 3pm Come by.')])
        self.assertEqual(stored[0]['dates'], {'start': dt.date(2026, 11, 20), 'end': dt.date(2026, 11, 30)})
        self.assertEqual(stored[0]['phase'], 'future')

    def test_past_shows_classes_and_an_unreachable_page_store_nothing(self):
        self.assertEqual(run([slide('Old', 'Show Dates October 2nd – 31st Artist Reception October 3rd, Noon - 3pm Done.'),
                              slide('Class', 'Join the artist for a workshop. Date and Time Saturday, Nov 14')]), [])
        self.assertEqual(run(None), [])


if __name__ == '__main__':
    unittest.main()
