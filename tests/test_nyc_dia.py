# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Dia Chelsea (WEBSITE-121). The fixture is a trimmed copy of the page the paid proxy returned (with page rendering)
# on 2026-11-15. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import dia_art_foundation
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 15)
DOCS = os.path.join(os.path.dirname(__file__), '../docs/data')


def figure(slug, title, line, image='/media/w690h690/webimages/pic.jpg'):
    picture = f'<img alt="" src="{image}"/>' if image else ''
    return (f'<div><figure>{picture}<figcaption><h2><p>{title}</p></h2><p>{line}</p></figcaption>'
            f'<a href="https://diaart.org/exhibition/exhibitions-projects/{slug}">Move to <p>{title}</p> page</a></figure></div>')


def run(html):
    stored = []
    soup = BeautifulSoup(html, 'html.parser') if html is not None else None
    with mock.patch.object(dia_art_foundation, 'fetch_and_parse', return_value=soup), \
            mock.patch.object(dia_art_foundation, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        dia_art_foundation.scrape_dia_art_foundation(env='prod', region='nyc')
    return {e['name']: e for e in stored}


class DiaTest(unittest.TestCase):
    def test_keeps_only_shows_at_dia_chelsea_current_and_upcoming(self):
        html = ('<main>'
                + figure('haegue-yang', 'Haegue Yang: Through', 'October 10, 2026–June 12, 2028, Dia Beacon')
                + figure('david-lamelas', 'David Lamelas: The Machine', 'March 6, 2026–January 16, 2027, Dia Chelsea', image='')
                + figure('radigue', 'Éliane Radigue: States of Listening', 'Opening December 4, 2026, Dia Chelsea',
                         image='/media/w690h690/webimages/eliane radigue_2.jpg')
                + figure('warhol', 'Andy Warhol: Shadows', 'Opening September 17, 2027, Dia Chelsea')
                + figure('alan-ruiz', 'Alan Ruiz: De sol a sol', 'June 26, 2026–May 31, 2027, Dia Bridgehampton')
                + figure('earth-room', 'Walter De Maria, The New York Earth Room', '141 Wooster Street, New York')
                + figure('lee-ufan', 'Lee Ufan', 'May 9–November 22, 2026, Venice, Touring Exhibitions')
                + '</main>')
        shows = run(html)
        self.assertEqual(sorted(shows), ['Andy Warhol: Shadows', 'David Lamelas: The Machine', 'Éliane Radigue: States of Listening'])
        lamelas = shows['David Lamelas: The Machine']
        self.assertEqual((lamelas['dates']['start'], lamelas['dates']['end']), (dt.date(2026, 3, 6), dt.date(2027, 1, 16)))
        self.assertEqual(lamelas['links'][0]['link'], 'https://diaart.org/exhibition/exhibitions-projects/david-lamelas')
        radigue = shows['Éliane Radigue: States of Listening']
        self.assertEqual((radigue['dates']['start'], radigue['dates']['end']), (dt.date(2026, 12, 4), None))
        picture = next(link['link'] for link in radigue['links'] if link['description'] == 'Image')
        self.assertEqual(picture, 'https://diaart.org/media/w690h690/webimages/eliane%20radigue_2.jpg')

    def test_a_failed_fetch_keeps_existing_data(self):
        self.assertEqual(run(None), {})


class RegistryTest(unittest.TestCase):
    def test_dia_chelsea_is_registered_proxied_scheduled_and_has_its_data(self):
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
        self.assertIn('Dia Chelsea', scrapers)
        self.assertEqual(main.PROXIED_VENUES['Dia Chelsea'], ['Dia Chelsea'])
        self.assertTrue(utils.PROXY_DOMAINS['diaart.org']['js_render'])
        self.assertIn('Dia Chelsea', coordinates)
        self.assertIn('Dia Chelsea', admission)


if __name__ == '__main__':
    unittest.main()
