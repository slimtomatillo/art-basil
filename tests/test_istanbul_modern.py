# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Istanbul Modern's exhibition pages. The date used to come from one CSS selector that stopped matching when
# the site changed its markup, which left every show without dates. The date is now the first date-shaped text
# after the title. The fixtures are trimmed copies of the markup captured on 2026-11-13. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.ist import istanbul_modern as im

NEW_LAYOUT = ('<html><body><ul class="breadcrumb"><li>Exhibitions</li></ul><div class="row"><div class="exp_h col d-flex flex-column">'
              '<h1>{title}</h1><div>{date}</div></div></div><div class="share">Twitter Facebook</div>'
              '<p>Some description</p><p>September 22, 2026</p></body></html>')
# The layout of 2026-11-13: the header block above the <h1> holds the title, the date and the share links
REAL_LAYOUT = ('<html><body><ul class="breadcrumb"><li>Exhibitions</li></ul><div class="row"><div class="col-12"><div class="exp_h col d-flex flex-column">'
               '<div>{title}</div><div>{date}</div></div></div></div><div class="share">Twitter Facebook</div>'
               '<h1>{title}</h1><p>Some description</p><div class="inner_slide"><p>September 22, 2026</p></div></body></html>')
OLD_LAYOUT = ('<html><body><ul class="breadcrumb"><li>Exhibitions</li></ul><div class="pl-3">{date}</div>'
              '<h1>{title}</h1><p>Some description</p></body></html>')


def run(pages_by_slug, sections=None):
    """pages_by_slug: {slug: (section, html)}. Returns {name: stored event}."""
    listings = {s: '<html><body>' + ''.join(f'<a href="/en/exhibitions/{slug}">x</a>' for slug, (sec, _) in pages_by_slug.items() if sec == s) + '</body></html>'
                for s in ('current', 'upcoming', 'past')}
    pages = {f'{im.BASE_URL}/en/exhibitions/{s}': h for s, h in listings.items()}
    pages.update({f'{im.BASE_URL}/en/exhibitions/{slug}': html for slug, (_, html) in pages_by_slug.items()})
    stored = []
    with mock.patch.object(im, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(pages[url], 'html.parser') if url in pages else None), \
            mock.patch.object(im.time, 'sleep', lambda s: None), \
            mock.patch.object(im, 'process_event', lambda details, region: stored.append(details)):
        im.scrape_istanbul_modern_exhibitions(env='prod')
    return {e['name']: e for e in stored}


class IstanbulModernDatesTest(unittest.TestCase):
    def test_the_date_in_the_header_block_above_the_title_is_read(self):
        found = run({'blue': ('current', REAL_LAYOUT.format(title='Beneath the Same Blue', date='September 8, 2026'))})
        self.assertEqual(found['Beneath the Same Blue']['dates'], {'start': dt.date(2026, 9, 8), 'end': None})   # not the slider's date
        self.assertTrue(found['Beneath the Same Blue']['ongoing'])

    def test_a_lone_opening_date_after_the_title_is_a_long_running_show(self):
        found = run({'blue': ('current', NEW_LAYOUT.format(title='Beneath the Same Blue', date='September 8, 2026'))})
        show = found['Beneath the Same Blue']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 9, 8), 'end': None})
        self.assertEqual((show['phase'], show['ongoing']), ('current', True))

    def test_a_range_after_the_title_is_read(self):
        found = run({'x': ('current', NEW_LAYOUT.format(title='A Show', date='November 5, 2026–May 23, 2027'))})
        self.assertEqual(found['A Show']['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2027, 5, 23)})

    def test_an_upcoming_show_is_a_future_one(self):
        found = run({'x': ('upcoming', NEW_LAYOUT.format(title='Soon', date='January 22–November 22, 2099'))})
        self.assertEqual(found['Soon']['phase'], 'future')

    def test_the_old_layout_still_works(self):
        found = run({'x': ('current', OLD_LAYOUT.format(title='Old Layout', date='November 5, 2026–May 23, 2027'))})
        self.assertEqual(found['Old Layout']['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2027, 5, 23)})

    def test_a_page_with_no_date_keeps_the_phase_of_its_section(self):
        found = run({'x': ('upcoming', '<html><body><h1>No Date</h1><p>text</p></body></html>')})
        self.assertEqual(found['No Date']['dates'], {'start': None, 'end': None})
        self.assertEqual(found['No Date']['phase'], 'future')

    def test_a_date_further_down_the_page_is_not_taken(self):
        page = ('<html><body><h1>Title</h1>' + '<p>some words</p>' * 14 + '<p>September 22, 2026</p></body></html>')
        self.assertEqual(run({'x': ('current', page)})['Title']['dates'], {'start': None, 'end': None})


if __name__ == '__main__':
    unittest.main()
