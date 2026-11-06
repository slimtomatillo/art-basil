# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Marin Civic Center (WEBSITE-81). The page 403s scripted requests, so the
# fixture is a trimmed copy of its markup captured in a browser on 2026-11-05. No network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import main
import utils
from scrapers.sf import civic_center_art_gallery as gallery
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 5)

EXHIBIT = '''<div class="field__item"><div class="paragraph paragraph--type--rich-text"><div class="layout layout--onecol">
<div class="layout__region layout__region--content"><h2 id="x" class="usa-paragraph__title"><span>{title}</span></h2>
<div class="marin-prose field field--name-field-content"><h3>{dates}</h3>
<h4>Marin County Civic Center 1st and 3rd floor Galleries</h4>
<p dir="ltr">Marin's iconic Frank Lloyd Wright Civic Center becomes home to the work of Marin-based designers.</p>
<p dir="ltr">Known for their "rehabbed" luxury wear, this exhibit gathers their creative vision under one roof.</p></div></div></div></div></div>'''
IMAGE = '<div class="slideshow"><img src="https://assets.marincounty.gov/marincounty-prod/public/2026-09/WSMR_ivory.jpeg?VersionId=abc" alt="bodice top"></div>'
OTHER_BLOCKS = ('<div class="field__item"><h2 class="usa-paragraph__title"><span>Gallery Location and Hours</span></h2>'
                '<div class="marin-prose"><p>Marin Civic Center</p><p>9am to 6pm Monday through Friday</p></div></div>'
                '<h2>Related</h2><p>Bartolini Gallery</p>')


def page(*exhibits, image=IMAGE):
    return f'<main><article>{"".join(exhibits)}{image}{OTHER_BLOCKS}</article></main>'


def run(html):
    stored = []
    with mock.patch.object(gallery, 'fetch_and_parse', return_value=BeautifulSoup(html, 'html.parser') if html else None), \
            mock.patch.object(gallery, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        gallery.scrape_civic_center_art_gallery(env='prod')
    return stored


class CivicCenterTest(unittest.TestCase):
    ONE = EXHIBIT.format(title='When Simon Met Ralph: A Retrospective', dates='October 1, 2026, to January 7, 2027')

    def test_the_exhibit_is_read_with_dates_description_and_picture(self):
        stored = run(page(self.ONE))
        self.assertEqual(len(stored), 1)           # the hours and "Related" blocks are not exhibits
        show = stored[0]
        self.assertEqual(show['name'], 'When Simon Met Ralph: A Retrospective')
        self.assertEqual(show['venue'], 'Marin Civic Center')
        self.assertEqual(show['phase'], 'current')
        self.assertEqual(show['dates'], {'start': dt.date(2026, 10, 1), 'end': dt.date(2027, 1, 7)})
        self.assertIn('gallery', show['tags'])
        self.assertTrue(show['description'].startswith("Marin's iconic Frank Lloyd Wright"))
        self.assertEqual(show['links'][0], {'link': gallery.PAGE_URL, 'description': 'Event Page'})
        self.assertEqual([l['link'] for l in show['links'] if l['description'] == 'Image'],
                         ['https://assets.marincounty.gov/marincounty-prod/public/2026-09/WSMR_ivory.jpeg?VersionId=abc'])

    def test_an_upcoming_exhibit_is_future(self):
        html = page(EXHIBIT.format(title='Next Show', dates='January 15, 2027, to April 2, 2027'))
        self.assertEqual(run(html)[0]['phase'], 'future')

    def test_with_two_exhibits_the_one_picture_is_not_guessed_for_either(self):
        stored = run(page(self.ONE, EXHIBIT.format(title='Next Show', dates='January 15, 2027, to April 2, 2027')))
        self.assertEqual(len(stored), 2)
        self.assertTrue(all('Image' not in [l['description'] for l in d['links']] for d in stored))

    def test_an_exhibit_without_readable_dates_is_skipped(self):
        self.assertEqual(run(page(EXHIBIT.format(title='Mystery', dates='Coming soon'))), [])

    def test_unreachable_page_stores_nothing(self):
        self.assertEqual(run(None), [])


class RegistrationTest(unittest.TestCase):
    """The three places a new venue must be listed besides its scraper (ADDING_A_REGION.md)."""

    def test_registered_proxied_and_has_an_address(self):
        scrapers, regions = main.get_venue_scrapers(selected_regions=['sf'])
        self.assertIn('Marin Civic Center', scrapers)
        self.assertEqual(main.PROXIED_VENUES['Marin Civic Center'], [gallery.VENUE])   # else it would run daily
        self.assertIn('www.marincounty.gov', utils.PROXY_DOMAINS)
        with open(os.path.join(os.path.dirname(__file__), '../docs/data/sf_venues.json')) as f:
            venues = json.load(f)
        self.assertIn(gallery.VENUE, venues)                                                # else no map link


if __name__ == '__main__':
    unittest.main()
