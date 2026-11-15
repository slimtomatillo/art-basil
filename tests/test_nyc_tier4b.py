# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York tier 4, second batch (WEBSITE-121): Asia Society Museum, El Museo del Barrio and the Museum of the Moving
# Image, fetched through the paid proxy. Fixtures are trimmed copies of the markup the sites served a browser on
# 2026-11-15. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import asia_society_museum, el_museo_del_barrio, museum_of_the_moving_image
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 15)
DOCS = os.path.join(os.path.dirname(__file__), '../docs/data')


def run(module, scrape, pages):
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region='nyc')
    return {e['name']: e for e in stored}


def image_of(event):
    return next((link['link'] for link in event['links'] if link['description'] == 'Image'), None)


def asia_card(slug, title, dates, description):
    return (f'<div><div><div><a href="/new-york/exhibitions/{slug}"><img src="/sites/default/files/styles/400x286/public/{slug}.jpg" alt="x"></a></div></div>'
            f'<div><div><h4><a href="/new-york/exhibitions/{slug}" rel="bookmark"><div>{title}</div></a></h4></div>'
            f'<div>{dates} </div><div><div>{description}</div></div></div></div>')


class AsiaSocietyTest(unittest.TestCase):
    def test_reads_day_first_dates_titles_links_and_pictures(self):
        current = ('<main><a href="/new-york/exhibitions">Upcoming Exhibitions</a>'
                   + asia_card('busy-busy-towns', 'Busy, Busy Towns', '18 Mar 2026 - 03 Jan 2027',
                               'These video works explore how rapidly evolving cultural, political and ecological issues have shaped cities.')
                   + asia_card('legacy-continued', 'A Legacy Continued: Recent Acquisitions', '05 Feb 2026 - 14 Mar 2027', 'Short.')
                   + '</main>')
        upcoming = '<main><h2>Upcoming Exhibitions</h2></main>'
        shows = run(asia_society_museum, 'scrape_asia_society_museum',
                    {asia_society_museum.PAGES[0]: current, asia_society_museum.PAGES[1]: upcoming})
        self.assertEqual(sorted(shows), ['A Legacy Continued: Recent Acquisitions', 'Busy, Busy Towns'])
        busy = shows['Busy, Busy Towns']
        self.assertEqual((busy['dates']['start'], busy['dates']['end']), (dt.date(2026, 3, 18), dt.date(2027, 1, 3)))
        self.assertEqual(busy['links'][0]['link'], 'https://asiasociety.org/new-york/exhibitions/busy-busy-towns')
        self.assertEqual(image_of(busy), 'https://asiasociety.org/sites/default/files/styles/400x286/public/busy-busy-towns.jpg')
        self.assertTrue(busy['description'].startswith('These video works explore'))

    def test_a_failed_fetch_keeps_existing_data(self):
        self.assertEqual(run(asia_society_museum, 'scrape_asia_society_museum', {}), {})


def museo_card(slug, title, dates):
    return (f'<div><div><div><a href="https://elmuseo.org/exhibition/{slug}/"><img src="https://elmuseo.org/wp-content/uploads/2025/11/{slug}.jpg" alt="x"></a></div></div>'
            f'<div><div><div>{dates}</div></div></div><div><div><h3><a href="https://elmuseo.org/exhibition/{slug}/">{title}</a></h3></div></div></div>')


class ElMuseoTest(unittest.TestCase):
    def test_keeps_current_and_upcoming_and_drops_ended_shows(self):
        html = ('<main><h2>On View</h2>' + museo_card('new-show', 'A New Show', 'November 5, 2026 — March 14, 2027')
                + '<h2>Upcoming</h2>' + museo_card('later', 'Coming Later', 'April 9 – August 1, 2027')
                + '<h2>Past Exhibitions</h2>' + museo_card('sophie-rivera', 'Sophie Rivera: Double Exposures', 'April 23 – August 2, 2026')
                + '</main>')
        shows = run(el_museo_del_barrio, 'scrape_el_museo_del_barrio', {el_museo_del_barrio.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['A New Show', 'Coming Later'])
        new = shows['A New Show']
        self.assertEqual((new['dates']['start'], new['dates']['end']), (dt.date(2026, 11, 5), dt.date(2027, 3, 14)))
        self.assertEqual(new['links'][0]['link'], 'https://elmuseo.org/exhibition/new-show/')
        self.assertTrue(image_of(new).endswith('new-show.jpg'))


def moi_block(title, dates, description):
    return (f'<div><div><div><img src="https://movingimage.org/wp-content/uploads/2026/11/x.png" alt=""></div></div>'
            f'<div><h2>{title}</h2><div><p>{dates}</p></div><div><p>{description}</p></div></div></div>')


class MovingImageTest(unittest.TestCase):
    def test_reads_only_the_current_section_and_skips_blocks_without_a_run(self):
        html = ('<main><h2>Search Museum of the Moving Image</h2><h2>CURRENT EXHIBITIONS</h2>'
                + moi_block('Doom Drop', 'November 12, 2026–January 3, 2027', 'An independent video game in a custom arcade cabinet.')
                + moi_block('Seeing the Cinema:&nbsp;Photographic Visions of Movie Theaters', 'October 10, 2026–March 21, 2027', 'This exhibition explores the movie theater.')
                + moi_block('Site Interruptions', 'July 2 2026–July 25, 2027&nbsp;', 'A series of artist commissions.')
                + moi_block('The Jim Henson Exhibition', '', 'A permanent display.')
                + '<h2>EXHIBITION ARCHIVE</h2>' + moi_block('Old Show', 'January 1, 2025–March 1, 2025', 'Gone.') + '</main>')
        shows = run(museum_of_the_moving_image, 'scrape_museum_of_the_moving_image', {museum_of_the_moving_image.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['Doom Drop', 'Seeing the Cinema: Photographic Visions of Movie Theaters', 'Site Interruptions'])
        doom = shows['Doom Drop']
        self.assertEqual((doom['dates']['start'], doom['dates']['end']), (dt.date(2026, 11, 12), dt.date(2027, 1, 3)))
        self.assertEqual(doom['links'][0]['link'], 'https://movingimage.org/whats-on/exhibitions/')
        self.assertTrue(image_of(doom).endswith('x.png'))
        self.assertEqual(doom['description'], 'An independent video game in a custom arcade cabinet.')


class RegistryTest(unittest.TestCase):
    VENUES = {'Asia Society Museum': 'asiasociety.org', 'El Museo del Barrio': 'elmuseo.org',
              'Museum of the Moving Image': 'movingimage.org'}

    def test_each_venue_is_registered_proxied_scheduled_and_has_its_data(self):
        import main
        import utils
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(DOCS, 'venue_coordinates.json'), encoding='utf-8') as f:
            coordinates = json.load(f)['nyc']
        with open(os.path.join(DOCS, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['nyc']
        self.assertEqual(sorted(scrapers), sorted(venues))
        for venue, host in self.VENUES.items():
            self.assertIn(venue, scrapers)
            self.assertIn(host, utils.PROXY_DOMAINS)
            self.assertEqual(main.PROXIED_VENUES[venue], [venue])
            self.assertIn(venue, coordinates)
            self.assertIn(venue, admission, f'{venue} needs an admission record')


if __name__ == '__main__':
    unittest.main()
