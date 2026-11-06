# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Oakland Photo Workshop (the East Bay Photo Collective's gallery, read from its Squarespace JSON feed)
# GearBox Gallery (read from its home page) and FM Oakland (the main block of its home page), WEBSITE-98. No network, no event data.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import main
from scrapers.sf import fm_oakland, gearbox_gallery, oakland_photo_workshop as opw
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 5)
UTC = dt.timezone.utc


def ms(*args):
    return str(int(dt.datetime(*args, tzinfo=UTC).timestamp() * 1000))


def item(title, start, end, address='312 8th Street', picture='https://images.squarespace-cdn.com/x/poster.png', **extra):
    return {'title': title, 'fullUrl': '/exhibitions-calendar/' + title.lower().replace(' ', '-'),
            'startDate': start, 'endDate': end, 'assetUrl': picture, 'excerpt': '<p>What happens <em>next</em>?</p>',
            'location': {'addressTitle': 'Oakland Photo Workshop' if address else '', 'addressLine1': address}, **extra}


class FakeResponse:
    def __init__(self, data=None, error=None):
        self.data, self.error = data, error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.data


def run_opw(data=None, error=None):
    stored = []
    with mock.patch.object(opw.requests, 'get', return_value=FakeResponse(data, error)), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        opw.scrape_oakland_photo_workshop(env='prod')
    return {d['name']: d for d in stored}


class OaklandPhotoWorkshopTest(unittest.TestCase):
    def test_dates_are_pacific_not_utc(self):
        # a 6 PM Pacific opening on Oct 2 is 01:00 UTC on Oct 3; a 3 PM Pacific close on Nov 15 is 23:00 UTC
        shows = run_opw({'upcoming': [item('Material as Witness', ms(2026, 10, 3, 1), ms(2026, 11, 15, 23))]})
        show = shows['Material as Witness']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 10, 2), 'end': dt.date(2026, 11, 15)})
        self.assertEqual(show['phase'], 'current')
        self.assertEqual(show['links'][0], {'link': 'https://www.ebpco.org/exhibitions-calendar/material-as-witness',
                                            'description': 'Event Page'})
        self.assertEqual(show['links'][1], {'link': 'https://images.squarespace-cdn.com/x/poster.png?format=750w',
                                            'description': 'Image'})
        self.assertEqual(show['description'], 'What happens next?')

    def test_shows_elsewhere_and_notices_are_skipped_but_a_blank_location_is_kept(self):
        data = {'upcoming': [
            item('At The Gallery', ms(2026, 12, 1, 1), ms(2027, 1, 10, 1)),
            item('No Location Given', ms(2026, 12, 1, 1), ms(2027, 1, 10, 1), address=''),
            item('Held Elsewhere', ms(2026, 12, 1, 1), ms(2027, 1, 10, 1), address='1900 Mandela Parkway'),
            item('NOTICE', ms(2026, 12, 1, 1), ms(2027, 1, 10, 1))]}
        self.assertEqual(sorted(run_opw(data)), ['At The Gallery', 'No Location Given'])

    def test_a_show_with_no_dates_or_picture_is_handled(self):
        data = {'upcoming': [item('Undated', None, None), item('No Picture', ms(2026, 12, 1, 8), ms(2027, 1, 10, 8), picture=None)]}
        shows = run_opw(data)
        self.assertEqual(list(shows), ['No Picture'])
        self.assertNotIn('Image', [l['description'] for l in shows['No Picture']['links']])

    def test_unreachable_or_broken_feed_stores_nothing(self):
        self.assertEqual(run_opw(error=requests.ConnectionError('down')), {})
        self.assertEqual(run_opw({'upcoming': None}), {})


HOME = '''<main><p>Open Thurs - Sat, 12-5 pm</p><h2>2026 Bay Area Open</h2>
<h2><strong>Tilt Toward Joy</strong></h2><p>Jenny Hacker and Maricris Briones Hansen</p><p>November 5 - December 19, 2026</p>
<p>Opening Reception</p><p>Sat, Nov 7th, 1-4 pm</p><a href="/tilt-toward-joy">More About Tilt Toward Joy</a>
<p>with special exhibition in the Inner Room</p>
<h2>Second Sight</h2><p>Joy Every</p><p>November 5 - December 19, 2026</p><a href="/joyeverysecondsight">More about Second Sight</a>
<a href="/past-exhibitions">PAST EXHIBITIONS</a></main>'''


def run_gearbox(html):
    stored = []
    with mock.patch.object(gearbox_gallery, 'fetch_and_parse', return_value=BeautifulSoup(html, 'html.parser') if html else None), \
            mock.patch.object(gearbox_gallery, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        gearbox_gallery.scrape_gearbox_gallery(env='prod')
    return {d['name']: d for d in stored}


class GearBoxTest(unittest.TestCase):
    def test_both_shows_are_read_with_their_own_pages(self):
        shows = run_gearbox(HOME)
        self.assertEqual(sorted(shows), ['Second Sight', 'Tilt Toward Joy'])
        joy = shows['Tilt Toward Joy']
        self.assertEqual(joy['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 12, 19)})
        self.assertEqual(joy['phase'], 'current')
        self.assertEqual(joy['links'][0]['link'], 'https://www.gearboxgallery.com/tilt-toward-joy')
        self.assertEqual(shows['Second Sight']['links'][0]['link'], 'https://www.gearboxgallery.com/joyeverysecondsight')

    def test_a_show_without_its_own_page_links_the_home_page(self):
        shows = run_gearbox(HOME.replace('<a href="/joyeverysecondsight">More about Second Sight</a>', ''))
        self.assertEqual(shows['Second Sight']['links'][0]['link'], 'https://www.gearboxgallery.com/')

    def test_page_with_no_shows_or_unreachable_stores_nothing(self):
        self.assertEqual(run_gearbox('<main><p>Closed for the holidays</p></main>'), {})
        self.assertEqual(run_gearbox(None), {})


FM_HOME = '''<main><div class="page"><div class="media-and-info"><a class="page-media"><img class="u-img" src="//img-cache.oppcdn.com/fixed/21686/assets/cowboy.jpg"></a></div>
<div class="description t-full-width"><p><br><br>For October/November FM Oakland is excited to host the recent works by local Berkeley native Paul Thompson. {intro}</p>
<p>{title}  <br>\u201cI always played cowboys and indians with my brother as a kid, and our father loved westerns.\u201d</p>
<p>{run}</p><p>Art Murmur Receptions:</p><p>First Friday, October 2nd, 5-10pm</p></div></div></main>'''
INTRO = "Thompson's work focuses on the romance and excitement of the wild west as he plays with paint, line, brushwork and composition."


def fm_page(title='Paul Thompson: Life of a Cowboy', run='October 2nd - November 28th, 2026'):
    return FM_HOME.format(title=title, run=run, intro=INTRO)


def run_fm(html):
    stored = []
    with mock.patch.object(fm_oakland, 'fetch_and_parse', return_value=BeautifulSoup(html, 'html.parser') if html else None), \
            mock.patch.object(fm_oakland, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        fm_oakland.scrape_fm_oakland(env='prod')
    return stored


class FmOaklandTest(unittest.TestCase):
    def test_the_current_exhibit_is_read_from_the_main_block(self):
        stored = run_fm(fm_page())
        self.assertEqual(len(stored), 1)
        show = stored[0]
        self.assertEqual(show['name'], 'Paul Thompson: Life of a Cowboy')       # not the artist's quoted statement
        self.assertEqual(show['dates'], {'start': dt.date(2026, 10, 2), 'end': dt.date(2026, 11, 28)})
        self.assertEqual(show['phase'], 'current')
        self.assertTrue(show['description'].startswith('For October/November FM Oakland is excited'))
        self.assertEqual(show['links'][1], {'link': 'https://img-cache.oppcdn.com/fixed/21686/assets/cowboy.jpg',
                                            'description': 'Image'})

    def test_title_and_dates_on_one_line_still_read(self):
        stored = run_fm(fm_page(title='Okamoto & Cibrian - \u201cDreamscapes\u201d April 3rd, \u2013 May 30th, 2027', run='Opening Friday'))
        self.assertEqual(stored[0]['name'], 'Okamoto & Cibrian - \u201cDreamscapes\u201d')
        self.assertEqual(stored[0]['dates'], {'start': dt.date(2027, 4, 3), 'end': dt.date(2027, 5, 30)})

    def test_an_ended_exhibit_is_not_published(self):
        self.assertEqual(run_fm(fm_page(run='October 2nd - October 30th, 2026')), [])

    def test_a_page_without_a_dated_exhibit_or_unreachable_stores_nothing(self):
        self.assertEqual(run_fm('<main><div class="page"><div class="description"><p>Coming soon</p></div></div></main>'), [])
        self.assertEqual(run_fm(None), [])


class RegistrationTest(unittest.TestCase):
    def test_registered_and_has_an_address(self):
        scrapers, _ = main.get_venue_scrapers(selected_regions=['sf'])
        with open(os.path.join(os.path.dirname(__file__), '../docs/data/sf_venues.json')) as f:
            venues = json.load(f)
        for venue in (opw.VENUE, gearbox_gallery.VENUE, fm_oakland.VENUE):
            self.assertIn(venue, scrapers)
            self.assertIn(venue, venues)        # else no map link


if __name__ == '__main__':
    unittest.main()
