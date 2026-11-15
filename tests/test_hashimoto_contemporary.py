# Run with the project's Python: python -m unittest discover -s tests
#
# Hashimoto Contemporary (WEBSITE-123): its "current" and "upcoming" pages became one exhibition's page each, and the
# scraper (which read a list) found nothing. Fixtures are trimmed copies of the pages captured on 2026-11-14. No network.
import datetime as dt
import html
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import hashimoto_contemporary as hashimoto

TODAY = dt.date(2026, 11, 14)


def exhibition_page(name, dates, location, slug):
    return (f'<html><head><meta property="og:title" content="{html.escape(name)} | {dates}">'
            f'<link href="https://www.hashimotocontemporary.com/exhibitions/{slug}/" rel="canonical"></head>'
            f'<body><h1 class="has_subtitle"><span class="h1_heading">{name}</span></h1>'
            f'<span class="location"><a href="/contact/">{location}</a></span></body></html>')


CURRENT = exhibition_page('Pat Perry - "WHILST"', '14 November - 5 December 2026', 'Hashimoto Contemporary NYC', '318-pat-perry-whilst')
FORTHCOMING = exhibition_page('James Eddy - "Figments of the Imagination"', '5 December 2026 - 2 January 2027',
                              'Hashimoto Contemporary SF', '324-james-eddy-figments-of-the-imagination')
LIST_ITEM = ('<ul><li><a href="/exhibitions/330-a-show/"><div class="content"><h2>A Show</h2><span class="date">2 Oct - 19 Dec 2026</span>'
             '<span class="location">Hashimoto Contemporary SF</span></div></a></li></ul>')


def run(pages):
    stored = []
    fetch = lambda url, *a, **k: BeautifulSoup(pages[url], 'html.parser') if url in pages else None
    with mock.patch.object(hashimoto, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(hashimoto, 'region_today', return_value=TODAY), \
            mock.patch.object(hashimoto, 'process_event', side_effect=lambda d, r: stored.append(d)):
        hashimoto.scrape_hashimoto_contemporary(env='prod')
    return stored


class HashimotoTest(unittest.TestCase):
    def test_a_single_exhibition_page_gives_its_show(self):
        item = hashimoto.single_exhibition(BeautifulSoup(FORTHCOMING, 'html.parser'))
        self.assertEqual(item['name'], 'James Eddy - "Figments of the Imagination"')
        self.assertEqual(item['date_text'], '5 December 2026 - 2 January 2027')
        self.assertEqual(item['location'], 'Hashimoto Contemporary SF')
        self.assertEqual(item['link'], 'https://www.hashimotocontemporary.com/exhibitions/324-james-eddy-figments-of-the-imagination/')

    def test_a_page_with_no_exhibition_on_it_gives_none(self):
        self.assertIsNone(hashimoto.single_exhibition(BeautifulSoup('<html><body><h1>Oops</h1></body></html>', 'html.parser')))

    def test_the_san_francisco_show_is_kept_and_the_new_york_one_left_out(self):
        stored = run({hashimoto.PAGES[0]: CURRENT, hashimoto.PAGES[1]: FORTHCOMING})
        self.assertEqual([e['name'] for e in stored], ['James Eddy - "Figments of the Imagination"'])
        show = stored[0]
        self.assertEqual(show['dates'], {'start': dt.date(2026, 12, 5), 'end': dt.date(2027, 1, 2)})
        self.assertEqual(show['phase'], 'future')
        self.assertEqual(show['links'][0]['link'], 'https://www.hashimotocontemporary.com/exhibitions/324-james-eddy-figments-of-the-imagination/')

    def test_a_list_page_is_still_read_as_a_list(self):
        stored = run({hashimoto.PAGES[0]: f'<html><body>{LIST_ITEM}</body></html>', hashimoto.PAGES[1]: FORTHCOMING})
        self.assertEqual(sorted(e['name'] for e in stored), ['A Show', 'James Eddy - "Figments of the Imagination"'])


if __name__ == '__main__':
    unittest.main()
