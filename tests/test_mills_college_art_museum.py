# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Mills College Art Museum (WEBSITE-99). The page 403s scripted requests, so the fixture is a trimmed copy
# of its markup captured in a browser on 2026-11-09. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import main
import utils
from scrapers.sf import mills_college_art_museum as mills
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 9)

PAGE = '''<main><div class="entry-content">
<div class="sidebar"><h2><a href="https://mcam.oakland.northeastern.edu/exhibitions/">Overview</a></h2><h2>Current</h2>
<p><a href="https://mcam.oakland.northeastern.edu/about/the-data-at-hand-upcoming/">The Data at Hand</a></p></div>
<div class="wp-block-columns"><div class="wp-block-column"><div class="wp-block-group">
<h2 class="wp-block-heading status">CURRENT</h2>
<div class="wp-block-group"><figure class="wp-block-image"><img src="https://mcam.oakland.northeastern.edu/wp-content/uploads/2026/01/Landing_Exhibitions_Data-1.png" alt=""></figure></div>
<h2 class="wp-block-heading h2title"><strong><strong>SEP 12-DEC 6, 2026</strong></strong></h2>
<h3 class="wp-block-heading"><a href="https://mcam.oakland.northeastern.edu/about/the-data-at-hand-upcoming/">THE DATA AT HAND: DATA PHYSICALIZATIONS OF EARTH AND SPACE</a></h3>
<p class="more wp-block-paragraph">Contemporary artists combining traditional craft materials and practices with data information.<em>&nbsp;</em></p>
</div></div></div>
<div class="wp-block-columns"><div class="wp-block-column"><div class="wp-block-group">
<h2 class="wp-block-heading status">UPCOMING</h2>
<div class="wp-block-group"><figure class="wp-block-image"><img loading="lazy" src="https://mcam.oakland.northeastern.edu/wp-content/uploads/2026/10/Oliveros_Pauline_Buchla.jpeg" alt=""></figure></div>
<h2 class="wp-block-heading h2title"><strong>JAN 19-MAY 9, 202</strong>7</h2>
<h3 class="wp-block-heading"><strong><a href="https://mcam.oakland.northeastern.edu/about/material-frequencies/">MATERIAL FREQUENCIES</a></strong></h3>
<p class="more wp-block-paragraph">A Bay Area survey exploring electroacoustic music and sound art.</p>
</div></div></div></div></main>'''


def run(html):
    stored = []
    with mock.patch.object(mills, 'fetch_and_parse', return_value=BeautifulSoup(html, 'html.parser') if html else None), \
            mock.patch.object(mills, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        mills.scrape_mills_college_art_museum(env='prod')
    return {e['name']: e for e in stored}


class MillsTest(unittest.TestCase):
    def test_current_and_upcoming_shows(self):
        events = run(PAGE)
        self.assertEqual(set(events), {'The Data at Hand: Data Physicalizations of Earth and Space', 'Material Frequencies'})
        current = events['The Data at Hand: Data Physicalizations of Earth and Space']
        self.assertEqual(current['dates'], {'start': dt.date(2026, 9, 12), 'end': dt.date(2026, 12, 6)})
        self.assertEqual(current['phase'], 'current')
        self.assertEqual(current['venue'], 'Mills College Art Museum')
        self.assertIn('museum', current['tags'])
        self.assertEqual(current['description'], 'Contemporary artists combining traditional craft materials and practices with data information.')
        self.assertIn({'link': 'https://mcam.oakland.northeastern.edu/about/the-data-at-hand-upcoming/', 'description': 'Event Page'}, current['links'])
        self.assertIn({'link': 'https://mcam.oakland.northeastern.edu/wp-content/uploads/2026/01/Landing_Exhibitions_Data-1.png', 'description': 'Image'}, current['links'])

    def test_a_date_split_across_tags_is_read_whole(self):
        upcoming = run(PAGE)['Material Frequencies']
        self.assertEqual(upcoming['dates'], {'start': dt.date(2027, 1, 19), 'end': dt.date(2027, 5, 9)})
        self.assertEqual(upcoming['phase'], 'future')

    def test_the_museum_is_tagged_free(self):
        # Always free (docs/data/venue_admission.json), so the shared tagging rule adds the tag
        import tagging
        self.assertIn('Mills College Art Museum', tagging.free_venues())

    def test_unreadable_page_keeps_existing_data(self):
        self.assertEqual(run(None), {})
        self.assertEqual(run('<main><h2>Nothing here</h2></main>'), {})

    def test_it_is_registered_and_fetched_through_the_proxy(self):
        venues, regions = main.get_venue_scrapers()
        self.assertIn('Mills College Art Museum', venues)
        self.assertEqual(regions['Mills College Art Museum'], 'sf')
        self.assertIn('mcam.oakland.northeastern.edu', utils.PROXY_DOMAINS)
        self.assertIn('Mills College Art Museum', main.PROXIED_VENUES)


if __name__ == '__main__':
    unittest.main()
