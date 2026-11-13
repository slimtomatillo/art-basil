# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Johansson Projects (ArtCloud JSON feed), Gray Loft Gallery (home page text block) and Dictée Art &
# Exhibition (home page announcement), from the Oakland Art Murmur venues (WEBSITE-99). No network, no data.
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
from scrapers.sf import dictee_art_exhibition as dictee, gray_loft_gallery as gray_loft, johansson_projects as johansson
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 6)


def soup(html):
    return BeautifulSoup(html, 'html.parser')


class FakeResponse:
    def __init__(self, data=None, text='', error=None):
        self.data, self.text, self.error = data, text, error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.data


def show(title, date, show_id, image=True):
    return {'title': title, 'date': date, 'showId': show_id, 'openingReception': None,
            'image': {'id': 'abc123', 'extension': 'jpg', 'width': 100, 'height': 100} if image else None}


class JohanssonTest(unittest.TestCase):
    SUB = '11111111-2222-3333-4444-555555555555'
    PAGE = '<script>ReactDOM.hydrate(x, {"config":{"subdomain":"%s"}})</script>' % SUB

    def run_scraper(self, shows=None, page=None, error=None):
        stored, calls = [], []

        def fake_get(url, params=None, **kwargs):
            calls.append((url, params))
            if url == johansson.API_URL:
                return FakeResponse({'shows': shows}, error=error)
            if isinstance(page, Exception):
                raise page
            return FakeResponse(text=page if page is not None else self.PAGE)

        with mock.patch.object(johansson.requests, 'get', side_effect=fake_get), \
                mock.patch.object(johansson, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
            johansson.scrape_johansson_projects(env='prod')
        return {d['name']: d for d in stored}, calls

    def test_shows_are_read_with_dates_page_and_picture(self):
        shows, calls = self.run_scraper([show('Gregory Rick // Night Watch', 'September 30 - November 14, 2026', 'jp-gregory-rick'),
                                         show('Sophie // Solo', 'January 16 - March 6, 2027', 'jp-sophie')])
        current = shows['Gregory Rick: Night Watch']
        self.assertEqual((current['phase'], current['dates']),
                         ('current', {'start': dt.date(2026, 9, 30), 'end': dt.date(2026, 11, 14)}))
        self.assertEqual(current['links'][0]['link'], 'https://johanssonprojects.com/show/jp-gregory-rick')
        self.assertEqual(current['links'][1]['link'], 'https://cdn.artcld.com/img/w_640,h_640,c_fit/abc123.jpg')
        self.assertEqual(shows['Sophie: Solo']['phase'], 'future')
        self.assertEqual(calls[-1][1]['sub'], self.SUB)               # the id is read from the page

    def test_past_shows_and_art_fair_booths_are_left_out(self):
        shows, _ = self.run_scraper([show('Untitled Miami 2026 ', 'December 1 - December 6, 2026', 'a'),
                                     show('Felix Art Fair // Annie Duncan', 'December 1 - December 6, 2026', 'b'),
                                     show('FOG 2026 // Miguel Arzabe', 'December 1 - December 6, 2026', 'c'),
                                     show('Old Show // Someone', 'June 4 - August 1, 2026', 'd'),
                                     show('Real Show // Someone', 'December 5, 2026 - January 9, 2027', 'e', image=False)])
        self.assertEqual(list(shows), ['Real Show: Someone'])
        self.assertNotIn('Image', [l['description'] for l in shows['Real Show: Someone']['links']])

    def test_falls_back_to_the_known_id_when_the_page_cannot_be_read(self):
        _, calls = self.run_scraper([show('A // B', 'December 5, 2026 - January 9, 2027', 'x')], page=requests.ConnectionError('down'))
        self.assertEqual(calls[-1][1]['sub'], johansson.FALLBACK_SUB)

    def test_a_failed_feed_stores_nothing(self):
        shows, _ = self.run_scraper(error=requests.HTTPError('403'))
        self.assertEqual(shows, {})


GRAY = '''<main><div class="sqs-block-html"><div class="sqs-html-content"><h3><strong>{run}</strong></h3>
<p><strong>Opening Reception:</strong> Saturday, September 26, 4:00 to 7:00 pm</p>
<p>We are delighted to present <strong><em>{title},</em></strong> an exhibit that brings together seven Bay Area women artists.</p>
<img src="https://images.squarespace-cdn.com/content/v1/x/poster+font.jpg"></div></div></main>'''


def run_page(module, scraper, html):
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', return_value=soup(html) if html else None), \
            mock.patch.object(module, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scraper)(env='prod')
    return stored


class GrayLoftTest(unittest.TestCase):
    def run_gray(self, html):
        return run_page(gray_loft, 'scrape_gray_loft_gallery', html)

    def test_title_dates_description_and_picture(self):
        stored = self.run_gray(GRAY.format(run='September 26 - November 14, 2026', title='Gestures of Willful Abandon'))
        self.assertEqual(len(stored), 1)
        show = stored[0]
        self.assertEqual(show['name'], 'Gestures of Willful Abandon')          # no trailing comma
        self.assertEqual(show['dates'], {'start': dt.date(2026, 9, 26), 'end': dt.date(2026, 11, 14)})
        self.assertEqual(show['phase'], 'current')
        self.assertTrue(show['description'].startswith('We are delighted to present Gestures of Willful Abandon'))
        self.assertEqual(show['links'][1], {'link': 'https://images.squarespace-cdn.com/content/v1/x/poster+font.jpg',
                                            'description': 'Image'})

    def test_an_ended_show_a_page_without_a_title_and_an_unreachable_page_store_nothing(self):
        self.assertEqual(self.run_gray(GRAY.format(run='June 1 - July 5, 2026', title='Old Show')), [])
        self.assertEqual(self.run_gray('<main><div><h3>September 26 - November 14, 2026</h3><p>Coming soon</p></div></main>'), [])
        self.assertEqual(self.run_gray(None), [])


DICTEE = '''<main><p>Rent Dictee</p><p>CALL FOR ARTISTS</p><h1>MEMORY,</h1><p>LONGING,</p><p>REMEMBERING</p>
<p>Homage to Theresa Hak Kyung Cha</p><p>A juried group exhibition exploring memory, language and exile.</p>
<p>{run}</p><p>Oakland, California</p><p>APPLY NOW</p></main>'''


class DicteeTest(unittest.TestCase):
    def run_dictee(self, html):
        return run_page(dictee, 'scrape_dictee_art_exhibition', html)

    def test_the_announced_exhibition_is_read(self):
        stored = self.run_dictee(DICTEE.format(run='January 23 – March 6, 2027'))
        self.assertEqual(len(stored), 1)
        show = stored[0]
        self.assertEqual(show['name'], 'Memory, Longing, Remembering: Homage to Theresa Hak Kyung Cha')
        self.assertEqual(show['dates'], {'start': dt.date(2027, 1, 23), 'end': dt.date(2027, 3, 6)})
        self.assertEqual(show['phase'], 'future')
        self.assertEqual(show['description'], 'A juried group exhibition exploring memory, language and exile.')

    def test_a_label_line_above_the_title_is_not_part_of_it_and_a_featuring_line_makes_the_description(self):
        # the home page's layout from 2026-11-13: "UPCOMING" over the title, no description paragraph,
        # and a "Featuring:" line after the dates
        page = ('<main><p>Rent Dictee</p><p>UPCOMING</p><h1>MEASURED TENSION</h1><p>A Group Exhibition of Prints</p>'
                '<p>November 14 – December 12, 2026</p>'
                '<p>Featuring: James Mitchell, Thierry Rosset, Deborah Sibony, Denise Owen, and Carol Brighton</p>'
                '<p>Opening Reception: Saturday, November 14 | 11 AM – 3 PM</p><p>EXPLORE THE EXHIBITION</p></main>')
        show = self.run_dictee(page)[0]
        self.assertEqual(show['name'], 'Measured Tension: A Group Exhibition of Prints')
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 14), 'end': dt.date(2026, 12, 12)})
        self.assertEqual(show['description'], 'A Group Exhibition of Prints. Featuring: James Mitchell, Thierry Rosset, '
                                              'Deborah Sibony, Denise Owen, and Carol Brighton.')

    def test_the_renamed_show_replaces_the_one_stored_under_its_old_upcoming_name(self):
        from processing import is_same_event
        old = {'name': 'Upcoming Measured Tension: A Group Exhibition of Prints', 'dates': {'start': '2026-11-14', 'end': '2026-12-12'},
               'links': [{'link': dictee.HOME_URL, 'description': 'Event Page'}]}
        new = {**old, 'name': 'Measured Tension: A Group Exhibition of Prints'}
        self.assertTrue(is_same_event(new, old))

    def test_the_sections_background_picture_is_stored_resized(self):
        info = '{&quot;imageData&quot;:{&quot;uri&quot;:&quot;7acfee_abc~mv2.png&quot;}}'
        page = (f'<section><wow-image data-image-info="{info}"><img alt="Textured Collage.png"/></wow-image>'
                + DICTEE.format(run='January 23 – March 6, 2027') + '</section>')
        show = self.run_dictee(page)[0]
        self.assertEqual(show['links'][1], {
            'link': 'https://static.wixstatic.com/media/7acfee_abc~mv2.png/v1/fit/w_640,h_640,q_85/picture.jpg',
            'description': 'Image'})

    def test_a_logo_or_a_picture_with_no_data_is_not_used(self):
        logo = '{&quot;imageData&quot;:{&quot;uri&quot;:&quot;logo~mv2.jpg&quot;}}'
        for tag in (f'<wow-image data-image-info="{logo}"><img alt="DICTEE LOGO"/></wow-image>',
                    '<wow-image data-image-info="not json"></wow-image>', '<wow-image></wow-image>'):
            show = self.run_dictee(f'<section>{tag}' + DICTEE.format(run='January 23 – March 6, 2027') + '</section>')[0]
            self.assertEqual(len(show['links']), 1)

    def test_no_dated_announcement_or_unreachable_page_stores_nothing(self):
        self.assertEqual(self.run_dictee('<main><p>CALL FOR ARTISTS</p><p>Coming soon</p></main>'), [])
        self.assertEqual(self.run_dictee(None), [])


class RegistrationTest(unittest.TestCase):
    def test_registered_and_has_an_address(self):
        scrapers, _ = main.get_venue_scrapers(selected_regions=['sf'])
        with open(os.path.join(os.path.dirname(__file__), '../docs/data/sf_venues.json')) as f:
            venues = json.load(f)
        for venue in (johansson.VENUE, gray_loft.VENUE, dictee.VENUE):
            self.assertIn(venue, scrapers)
            self.assertIn(venue, venues)


if __name__ == '__main__':
    unittest.main()
