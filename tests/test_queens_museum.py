# Run with the project's Python: python -m unittest discover -s tests
#
# Queens Museum (WEBSITE-121, tier 1). The fixtures are trimmed copies of its pages' text captured on 2026-11-15
# (the show's title is only a line of text, with the artist on the line above; the run is month.day.year). No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import queens_museum
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 15)
BASE = 'https://queensmuseum.org'
BLURB = ('Sonia Boyce presents a new body of work that gathers singers, activists and archives in a film and installation '
         'about how a crowd learns to speak with one voice, made with the Resistance Revival Chorus.')


def show_page(lines):
    # a line starting with "!" is an image caption, which the site marks with the class forma-caption
    body = ''.join(f'<p class="forma-caption">{line[1:]}</p>' if line.startswith('!') else f'<p>{line}</p>' for line in lines)
    return f'<html><head><title>Queens Museum | x</title></head><body><main>{body}</main></body></html>'


SOLO = show_page(['Tickets', 'Exhibition', 'Sonia Boyce, Demonstrate', 'Exhibitions - Demonstrate', 'Sonia Boyce', 'Demonstrate',
                  '06.27.26 – 02.07.27', '!Sonia Boyce, "Demonstrate: What We Want," 2026. Photo credit: Aarony Bailey', BLURB])
GROUP = show_page(['Tickets', 'Exhibition', 'About Us: The American Imaginary', 'Exhibitions - About Us: The American Imaginary',
                   'About Us: The American Imaginary', '02.28.26 – 02.07.27', BLURB])
AIRPORT = show_page(['Tickets', 'Exhibition', 'Fred Wilson, Mother', 'Exhibitions - Mother', 'Fred Wilson', 'Mother', '06.01.22 – Ongoing', BLURB])
ENDED = show_page(['Tickets', 'Exhibition', 'Old Show', 'Exhibitions - Old Show', 'Old Show', '01.10.26 – 03.01.26', BLURB])
LISTING = ('<main>' + ''.join(f'<a href="{BASE}/exhibition/{slug}/">x</a>' for slug in ('demonstrate', 'about-us', 'mother', 'old-show'))
           + f'<a href="{BASE}/exhibitions/current">Current</a></main>')
PAGES = {queens_museum.LISTINGS[0]: LISTING, f'{BASE}/exhibition/demonstrate/': SOLO, f'{BASE}/exhibition/about-us/': GROUP,
         f'{BASE}/exhibition/mother/': AIRPORT, f'{BASE}/exhibition/old-show/': ENDED}


def run(pages):
    stored = []
    fetch = lambda url, *a, **k: BeautifulSoup(pages[url], 'html.parser') if url in pages else None
    with mock.patch.object(queens_museum, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(queens_museum, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        queens_museum.scrape_queens_museum(env='prod', region='nyc')
    return {e['name']: e for e in stored}


class QueensMuseumTest(unittest.TestCase):
    def test_a_solo_show_is_named_artist_then_title_and_a_group_show_by_its_title(self):
        events = run(PAGES)
        self.assertEqual(sorted(events), ['About Us: The American Imaginary', 'Sonia Boyce: Demonstrate'])
        solo = events['Sonia Boyce: Demonstrate']
        self.assertEqual(solo['dates'], {'start': dt.date(2026, 6, 27), 'end': dt.date(2027, 2, 7)})
        self.assertEqual(solo['venue'], 'Queens Museum')
        self.assertEqual(solo['links'][0]['link'], f'{BASE}/exhibition/demonstrate/')
        self.assertIn('museum', solo['tags'])
        self.assertTrue(solo['description'].startswith('Sonia Boyce presents'))

    def test_an_ongoing_airport_commission_and_an_ended_show_are_left_out(self):
        events = run(PAGES)
        self.assertNotIn('Fred Wilson: Mother', events)
        self.assertNotIn('Old Show', events)

    def test_a_page_with_no_dated_run_gives_none(self):
        self.assertIsNone(queens_museum.read_show(BeautifulSoup(show_page(['Tickets', 'Exhibition', 'Something']), 'html.parser'), TODAY))

    def test_the_museum_is_registered_with_an_address_and_coordinates(self):
        import json
        data = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
        self.assertIn('Queens Museum', json.load(open(os.path.join(data, 'nyc_venues.json'), encoding='utf-8')))
        self.assertIn('Queens Museum', json.load(open(os.path.join(data, 'venue_coordinates.json'), encoding='utf-8'))['nyc'])
        self.assertIn('Queens Museum', json.load(open(os.path.join(data, 'venue_admission.json'), encoding='utf-8'))['nyc'])
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        self.assertIn('Queens Museum', scrapers)


if __name__ == '__main__':
    unittest.main()
