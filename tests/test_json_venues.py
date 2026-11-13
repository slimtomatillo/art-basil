# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Daniel Faria Gallery and Jeffrey Deitch Los Angeles (WEBSITE-97): both sites fill their pages in with
# JavaScript from a public JSON endpoint, which the scrapers read directly. The fixtures are trimmed
# copies of the endpoints' answers captured on 2026-11-09. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import jeffrey_deitch
from scrapers.tor import _common, daniel_faria_gallery

TODAY = dt.date(2026, 11, 9)


def run(module, scrape, answer):
    stored = []
    with mock.patch.object(module, 'fetch_json', return_value=answer), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        scrape(env='prod')
    return {e['name']: e for e in stored}


def node(title, start, end, artists=(), uri='/exhibition/x/', image='https://api.danielfariagallery.com/pic.jpg',
         slug='x', content=None):
    return {'title': title, 'uri': uri, 'slug': slug, 'content': content,
            'featuredImage': {'node': {'url': image}} if image else None,
            'custom': {'startDate': start, 'endDate': end, 'artists': [{'name': a} for a in artists]}}


class DanielFariaTest(unittest.TestCase):
    def events(self, *nodes):
        return run(daniel_faria_gallery, daniel_faria_gallery.scrape_daniel_faria_gallery,
                   {'data': {'exhibitions': {'nodes': list(nodes)}}})

    def test_current_and_upcoming_shows(self):
        events = self.events(
            node('I is Another', 'November 12, 2026', 'December 19, 2026', ['Chris Curreri'], '/exhibition/i-is-another/',
                 slug='i-is-another'),
            node('Open Now', 'October 31, 2026', 'November 30, 2026', ['A', 'B']),
            node('Petrichor', 'September 18, 2026', 'October 31, 2026', ['Jennifer Rose Sciarrino']))
        self.assertEqual(set(events), {'Chris Curreri: I is Another', 'Open Now'})
        upcoming = events['Chris Curreri: I is Another']
        self.assertEqual(upcoming['phase'], 'future')
        self.assertEqual(upcoming['dates'], {'start': dt.date(2026, 11, 12), 'end': dt.date(2026, 12, 19)})
        self.assertEqual(upcoming['venue'], 'Daniel Faria Gallery')
        self.assertIn('gallery', upcoming['tags'])
        # the page is /exhibitions/<slug> on the site; the API's own uri (/exhibition/<slug>/) is a 404 there
        self.assertIn({'link': 'https://danielfariagallery.com/exhibitions/i-is-another', 'description': 'Event Page'}, upcoming['links'])
        self.assertIn({'link': 'https://api.danielfariagallery.com/pic.jpg', 'description': 'Image'}, upcoming['links'])
        self.assertEqual(events['Open Now']['phase'], 'current')

    def test_the_event_page_is_never_the_apis_own_address_which_is_a_404_on_the_site(self):
        events = self.events(node('I is Another', 'November 12, 2026', 'December 19, 2026', ['Chris Curreri'],
                                  uri='/exhibition/i-is-another/', slug='i-is-another'))
        links = [l['link'] for l in events['Chris Curreri: I is Another']['links'] if l['description'] == 'Event Page']
        self.assertEqual(links, ['https://danielfariagallery.com/exhibitions/i-is-another'])
        # without a slug the listing is the honest link
        events = self.events(node('No Slug', 'November 1, 2026', 'December 1, 2026', slug=None))
        self.assertEqual([l['link'] for l in events['No Slug']['links'] if l['description'] == 'Event Page'],
                         ['https://danielfariagallery.com/exhibitions'])

    def test_the_description_is_the_shows_own_text_from_the_api(self):
        html = ('<div>\n<div>\n<p><span class="font-avenir">Daniel Faria Gallery is pleased to present <em>I is Another</em>, '
                'Chris Curreri\u2019s sixth solo exhibition with the gallery.</span></p>\n'
                '<p><span>First presented at the Counterpublic Triennial in St. Louis, the work brings together sculpture and video.</span></p></div></div>')
        events = self.events(node('I is Another', 'November 12, 2026', 'December 19, 2026', ['Chris Curreri'], content=html),
                             node('Nothing Written', 'November 1, 2026', 'December 1, 2026', content=None),
                             node('Just a Date', 'November 2, 2026', 'December 2, 2026', content='<p>Opening reception November 12.</p>'))
        text = events['Chris Curreri: I is Another']['description']
        self.assertTrue(text.startswith('Daniel Faria Gallery is pleased to present I is Another, Chris Curreri\u2019s sixth solo exhibition'))
        self.assertIn('Counterpublic Triennial', text)
        self.assertNotIn('<', text)
        self.assertIsNone(events['Nothing Written']['description'])
        self.assertIsNone(events['Just a Date']['description'])                  # no prose in it

    def test_a_group_show_keeps_just_its_title(self):
        self.assertIn('Both Sides Now', self.events(node('Both Sides Now', 'October 1, 2026', 'December 1, 2026', ['A', 'B', 'C'])))

    def test_closed_for_installation_is_skipped(self):
        self.assertEqual(self.events(node('Closed for installation', 'November 3, 2026', 'November 11, 2026')), {})

    def test_a_show_without_a_picture_or_readable_dates(self):
        events = self.events(node('No Picture', 'November 1, 2026', 'December 1, 2026', image=None),
                             node('No Dates', None, None))
        self.assertEqual(set(events), {'No Picture'})
        self.assertEqual([l['description'] for l in events['No Picture']['links']], ['Event Page'])

    def test_an_unreadable_answer_keeps_existing_data(self):
        for answer in (None, {}, {'data': {'exhibitions': {'nodes': []}}}, {'errors': [{'message': 'x'}]}):
            self.assertEqual(run(daniel_faria_gallery, daniel_faria_gallery.scrape_daniel_faria_gallery, answer), {})


def show(title, opening, closing, text='<p>Opening reception: Friday, October 30, 6-8PM</p><p>A <em>wonderful</em> show.</p>',
         template='exhibition', files=None):
    return {'template': template, 'title': title, 'artists': 'Someone', 'openingdate': opening, 'closingdate': closing,
            'text': text, 'files': files if files is not None else
            {'a.jpg': {'type': 'image', 'url': '/content/a.jpg', 'sizes': {'500': '/thumbs/a-500.jpg', '1000': '/thumbs/a-1000.jpg'}}}}


class DeitchTest(unittest.TestCase):
    def events(self, state):
        return run(jeffrey_deitch, jeffrey_deitch.scrape_jeffrey_deitch, state)

    STATE = {
        '/los-angeles': {'template': 'home', 'title': 'Los Angeles', 'pages': []},
        '/los-angeles/exhibitions/now': show('Barry McGee: Another Round', '2026-10-30', '2027-01-30'),
        '/los-angeles/exhibitions/soon': show('Next Show', '2026-12-05', '2027-02-01'),
        '/los-angeles/exhibitions/old': show('Old Show', '2025-01-01', '2025-03-01'),
    }

    def test_current_and_upcoming_shows_only(self):
        events = self.events(self.STATE)
        self.assertEqual(set(events), {'Barry McGee: Another Round', 'Next Show'})
        now = events['Barry McGee: Another Round']
        self.assertEqual(now['phase'], 'current')
        self.assertEqual(now['dates'], {'start': dt.date(2026, 10, 30), 'end': dt.date(2027, 1, 30)})
        self.assertEqual(now['venue'], 'Jeffrey Deitch Los Angeles')
        self.assertIn('gallery', now['tags'])
        self.assertEqual(events['Next Show']['phase'], 'future')

    def test_link_picture_and_description(self):
        now = self.events(self.STATE)['Barry McGee: Another Round']
        self.assertIn({'link': 'https://www.deitch.com/los-angeles/exhibitions/now', 'description': 'Event Page'}, now['links'])
        self.assertIn({'link': 'https://www.deitch.com/thumbs/a-1000.jpg', 'description': 'Image'}, now['links'])
        self.assertEqual(now['description'], 'A wonderful show.')

    def test_a_show_with_no_closing_date_still_counts_from_its_opening(self):
        events = self.events({'/los-angeles/exhibitions/x': show('Open Ended', '2026-11-01', '')})
        self.assertEqual(events['Open Ended']['phase'], 'current')

    def test_an_unreadable_answer_keeps_existing_data(self):
        for answer in (None, [], {}):
            self.assertEqual(self.events(answer), {})


if __name__ == '__main__':
    unittest.main()
