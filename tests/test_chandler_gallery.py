# Run with the project's Python: python -m unittest discover -s tests
#
# Chandler Gallery (WEBSITE-130): its permanent San Francisco space at 1111 Geary opened on 2026-11-14. Fixtures are trimmed
# copies of the Artlogic markup its exhibitions page and a show page served on 2026-11-19. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import chandler_gallery
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 19)
BASE = 'https://chandler-gallery.com'


def item(slug, heading, subtitle, dates, teaser='Chandler Gallery is very pleased to present a show...'):
    return (f'<li><a href="/exhibitions/{slug}/overview/"><span class="image"><span><img alt="x" data-src="https://static-assets.artlogic.net/{slug}.jpg"></span></span>'
            f'<div class="content"><h2>{heading}</h2><span class="subtitle">{subtitle}</span><span class="date">{dates}</span>'
            f'<span class="description">{teaser}</span></div></a></li>')


LIST_PAGE = ('<html><body><span>On view</span><ul>'
             + item('22-aya-nakamura-grounding-a-solo-exhibition-at-1111-geary', 'Aya Nakamura', 'Grounding  |  A Solo Exhibition at 1111 Geary', '14 November - 18 December 2026')
             + '</ul><span>Upcoming</span><ul>'
             + item('23-patrick-dunford', 'Patrick Dunford', 'At 1111 Geary', '16 January - 27 February 2027')
             + item('24-emily-payne', 'Emily Payne', 'At 1111 Geary', '16 January - 27 February 2027')
             + '</ul><span>Past</span><ul>'
             + item('21-flora-fauna', 'Flora + Fauna', 'A Group Exhibition at Minnesota Street Project', '12 September - 24 October 2026')
             + item('19-the-whole-in-part', 'The Whole in Part', 'Mari Andrews', '28 March - 23 May 2026')
             + item('11-thither', 'Thither!', 'A Group Exhibition', '28 June - 9 August 2025')
             + '</ul></body></html>')


def show_page(title, description, image):
    return (f'<html><head><title>{title} | Chandler Gallery</title><meta property="og:description" content="{description}">'
            f'<meta property="og:image" content="{image}"></head><body><h1>{title}</h1><p>{description}</p></body></html>')


DESCRIPTION = ('Chandler Gallery is very pleased to present Grounding, an exhibition of drawings by Chicago-based artist Aya Nakamura, '
               'on view from November 14th through December 18th, 2026, at the gallery\'s new location at 1111 Geary Boulevard in San Francisco.')
PAGES = {
    BASE + '/exhibitions/': LIST_PAGE,
    BASE + '/exhibitions/22-aya-nakamura-grounding-a-solo-exhibition-at-1111-geary/overview/':
        show_page('Aya Nakamura: Grounding', DESCRIPTION, 'https://static-assets.artlogic.net/w_1200,h_630,c_fill/aya.jpg'),
}


def run(pages):
    stored, asked = [], []

    def fetch(url, *args, **kwargs):
        asked.append(url)
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(chandler_gallery, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(chandler_gallery, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        chandler_gallery.scrape_chandler_gallery(env='prod', region='sf')
    return {e['name']: e for e in stored}, asked


class SubtitleTest(unittest.TestCase):
    def test_title_and_place_are_told_apart(self):
        split = chandler_gallery.split_subtitle
        self.assertEqual(split('Grounding  |  A Solo Exhibition at 1111 Geary'), ('Grounding', '1111 Geary'))
        self.assertEqual(split('At 1111 Geary'), ('', '1111 Geary'))
        self.assertEqual(split('A Group Exhibition at Minnesota Street Project'), ('', 'Minnesota Street Project'))
        self.assertEqual(split('Mari Andrews'), ('Mari Andrews', ''))
        self.assertEqual(split('A Group Exhibition'), ('', ''))                   # describes the show, is no title
        self.assertEqual(split('Inaugural Exhibiton'), ('', ''))
        self.assertEqual(split(''), ('', ''))
        self.assertEqual(split(None), ('', ''))


class ChandlerGalleryTest(unittest.TestCase):
    def test_reads_the_shows_at_1111_geary_and_leaves_out_those_held_elsewhere(self):
        shows = list(chandler_gallery.read_shows(BeautifulSoup(LIST_PAGE, 'html.parser')))
        self.assertEqual([s[0] for s in shows], ['Aya Nakamura: Grounding', 'Patrick Dunford', 'Emily Payne',
                                                 'The Whole in Part: Mari Andrews', 'Thither!'])     # Flora + Fauna was at Minnesota Street Project
        self.assertEqual(shows[0][1:3], (dt.date(2026, 11, 14), dt.date(2026, 12, 18)))
        self.assertEqual(shows[0][3], BASE + '/exhibitions/22-aya-nakamura-grounding-a-solo-exhibition-at-1111-geary/overview/')

    def test_stores_the_current_and_upcoming_shows_with_a_description_and_picture(self):
        shows, asked = run(PAGES)
        self.assertEqual(sorted(shows), ['Aya Nakamura: Grounding', 'Emily Payne', 'Patrick Dunford'])
        aya = shows['Aya Nakamura: Grounding']
        self.assertEqual((aya['dates']['start'], aya['dates']['end']), (dt.date(2026, 11, 14), dt.date(2026, 12, 18)))
        self.assertEqual(aya['phase'], 'current')
        self.assertEqual(aya['venue'], 'Chandler Gallery')
        self.assertTrue(aya['description'].startswith('Chandler Gallery is very pleased to present Grounding'))
        self.assertTrue(any(link['description'] == 'Image' and link['link'].endswith('aya.jpg') for link in aya['links']))
        self.assertEqual(shows['Patrick Dunford']['phase'], 'future')
        # a past show's page is never asked for
        self.assertFalse(any('whole-in-part' in url or 'thither' in url or 'flora-fauna' in url for url in asked))

    def test_a_show_whose_page_cannot_be_fetched_is_still_stored_without_a_description(self):
        shows, _ = run({BASE + '/exhibitions/': LIST_PAGE})
        self.assertEqual(sorted(shows), ['Aya Nakamura: Grounding', 'Emily Payne', 'Patrick Dunford'])
        self.assertIsNone(shows['Emily Payne']['description'])

    def test_a_failed_fetch_of_the_list_keeps_existing_data(self):
        self.assertEqual(run({})[0], {})

    def test_a_show_with_dates_that_cannot_be_read_is_left_out(self):
        page = '<html><body><ul>' + item('9-x', 'Someone', 'At 1111 Geary', 'Opening soon') + '</ul></body></html>'
        self.assertEqual(list(chandler_gallery.read_shows(BeautifulSoup(page, 'html.parser'))), [])


if __name__ == '__main__':
    unittest.main()
