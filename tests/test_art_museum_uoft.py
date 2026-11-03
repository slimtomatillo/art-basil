# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.tor import _common
from scrapers.tor import art_museum_uoft as museum

TODAY = dt.date(2026, 11, 3)

# Trimmed copies of the museum's pages as they looked on 2026-11-03 (the site 403s scripts, so
# these were captured from a browser): "Upcoming Exhibitions" was empty, both touring shows were
# over, and the exhibitions page also lists touring and past shows that must be ignored.
EXHIBITIONS = '''<main><div class="section no-border" id="current"><h1>Current Exhibitions</h1>
<div class="grid-layout two-column"><div id="exhibition-38587" class="exhibition item current column">
<a href="https://artmuseum.utoronto.ca/exhibition/things-fall-apart/"><h3 class="item-title">Things Fall Apart</h3>
<p class="date">September 26, 2026–December 20, 2026</p></a></div></div></div>
<div class="section" id="upcoming"><h2>Upcoming Exhibitions</h2></div>
<div class="section touring-feed" id="touring"><div class="exhibition item touring column fourth-col">
<a href="https://artmuseum.utoronto.ca/exhibition/the-children-have-to-hear-another-story/"><h3 class="item-title">The Children Have to Hear Another Story</h3>
<p class="date">September 6, 2023–<br>November 25, 2023</p></a></div></div>
<div class="section" id="past"><h2>Past Exhibitions</h2><div class="exhibition item past year-2026">
<a href="https://artmuseum.utoronto.ca/exhibition/little-and-often/"><h3 class="item-title">Little and Often</h3>
<p class="date">May 7, 2026–August 1, 2026</p></a></div></div></main>'''

EXHIBITIONS_WITH_UPCOMING = EXHIBITIONS.replace(
    '<h2>Upcoming Exhibitions</h2></div>',
    '<h2>Upcoming Exhibitions</h2><div class="exhibition item upcoming column">'
    '<a href="https://artmuseum.utoronto.ca/exhibition/next-show/"><h3 class="item-title">Next Show</h3>'
    '<p class="date">January 20, 2027–<br>April 3, 2027</p></a></div></div>')

TOURING = '''<main><h1>Touring Exhibitions</h1><div class="section grid-layout" id="current">
<div class="description item"><p>In order to engage diverse and growing audiences...</p></div>
<div id="exhibition-31412" class="post item touring-exhibitions"><a href="https://artmuseum.utoronto.ca/exhibition/pizandawatc/">
<h3 class="item-title">Pizandawatc / The One Who Listens</h3><p class="date">January 17, 2024–March 23, 2024</p></a></div></div></main>'''

PROGRAMS = '''<main><h1>Current Programs</h1><div class="section grid-layout" id="current">
<div class="current-program-description description item"><p>The Art Museum produces a comprehensive program of events...</p></div>
<div id="program-39020" class="program item current"><a href="https://artmuseum.utoronto.ca/program/soft-calm-seed-quilts/">
<h3 class="item-title">Soft Calm: Seed Quilts Workshops</h3><p class="date">November 7, 2026–November 21, 2026</p></a></div>
<div id="program-39100" class="program item current"><a href="https://artmuseum.utoronto.ca/program/one-night/">
<h3 class="item-title">One Night Only</h3><p class="date">November 12, 2026</p></a></div></div>
<div class="section" id="past"><h2>Past Programs</h2><div class="program item past year-2026">
<a href="https://artmuseum.utoronto.ca/program/an-artist-talk-with-abbas-akhavan/"><h3 class="item-title">An Artist Talk with Abbas Akhavan</h3>
<p class="date">October 24, 2026</p></a></div></div></main>'''


def run(exhibitions=EXHIBITIONS):
    """Run the scraper over the fixture pages; returns the event dicts it would store."""
    pages = {
        museum.BASE_URL + '/exhibitions/': exhibitions,
        museum.BASE_URL + '/exhibition-type/touring-exhibitions/': TOURING,
        museum.BASE_URL + '/programs/': PROGRAMS,
    }
    stored = []
    with mock.patch.object(museum, 'fetch_and_parse', lambda url: BeautifulSoup(pages[url], 'html.parser')), \
            mock.patch.object(museum, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        museum.scrape_art_museum_uoft(env='prod')
    return {e['name']: e for e in stored}


class ArtMuseumTest(unittest.TestCase):
    def test_reads_the_current_exhibition_and_skips_touring_and_past_entries(self):
        # Pizandawatc (touring page) and The Children Have to Hear... / Little and Often (exhibitions page) are over
        self.assertEqual([n for n, e in run().items() if 'exhibition' in e['tags']], ['Things Fall Apart'])

    def test_an_empty_upcoming_section_adds_nothing(self):
        self.assertNotIn('future', {e['phase'] for e in run().values() if 'exhibition' in e['tags']})

    def test_an_upcoming_show_with_a_line_break_after_the_dash_is_read(self):
        show = run(EXHIBITIONS_WITH_UPCOMING)['Next Show']
        self.assertEqual((show['phase'], show['dates']['start'], show['dates']['end']),
                         ('future', dt.date(2027, 1, 20), dt.date(2027, 4, 3)))

    def test_programs_are_events_and_a_single_day_ends_the_same_day(self):
        events = {n: e for n, e in run().items() if 'event' in e['tags']}
        self.assertEqual(sorted(events), ['One Night Only', 'Soft Calm: Seed Quilts Workshops'])
        self.assertEqual(events['One Night Only']['dates'], {'start': dt.date(2026, 11, 12), 'end': dt.date(2026, 11, 12)})

    def test_everything_is_a_free_museum_listing(self):
        for event in run().values():
            self.assertIn('free', event['tags'])
            self.assertIn('museum', event['tags'])
            self.assertEqual(event['venue'], 'Art Museum at the University of Toronto')


if __name__ == '__main__':
    unittest.main()
