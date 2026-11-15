# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York, the rest of the readable tier 5 venues (WEBSITE-121): Jack Shainman Gallery, the Museum of Chinese in America and
# Sikkema Malloy Jenkins. Fixtures are trimmed copies of the markup the sites served on 2026-11-15. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import jack_shainman_gallery, museum_of_chinese_in_america, sikkema_malloy_jenkins
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


def shainman_page(title, dates, location, image='jackshainman.com/uploads/1/pic.jpg'):
    return (f'<html><head><title>{title} « Exhibitions « Jack Shainman Gallery</title><meta property="og:image" content="{image}"></head>'
            f'<body><nav>Menu</nav><h1>{title}</h1><p>{dates}</p><p>Location {location} Artists A B</p>'
            f'<p>An exhibition of new work that explores the artist\'s practice and its many sources in depth.</p></body></html>')


class JackShainmanTest(unittest.TestCase):
    def test_keeps_new_york_shows_with_their_space_and_leaves_out_the_school(self):
        listing = ('<main><a href="/exhibitions">Current</a><a href="/exhibitions/past">Past</a>'
                   '<a href="/exhibitions/donyel_ivyroyal">Donyel</a><a href="/exhibitions/modus_operandi">Modus Operandi</a></main>')
        base = 'https://jackshainman.com'
        pages = {jack_shainman_gallery.LISTING: listing,
                 f'{base}/exhibitions/donyel_ivyroyal': shainman_page('Donyel Ivy-Royal: By the time the rain', 'November 5 – December 19, 2026',
                                                                    '513 West 20th Street New York, NY 10011',
                                                                    'https://jackshainman.com/exhibitions/jackshainman.com/uploads/1/pic.jpg'),
                 f'{base}/exhibitions/modus_operandi': shainman_page('Modus Operandi', 'May 30 – November 28, 2026', '25 Broad Street Kinderhook, NY 12106')}
        shows = run(jack_shainman_gallery, 'scrape_jack_shainman_gallery', pages)
        self.assertEqual(list(shows), ['Donyel Ivy-Royal: By the time the rain'])
        show = shows['Donyel Ivy-Royal: By the time the rain']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (dt.date(2026, 11, 5), dt.date(2026, 12, 19)))
        self.assertEqual(show['locations'], ['513 West 20th Street'])
        self.assertEqual(image_of(show), 'https://jackshainman.com/uploads/1/pic.jpg')


def moca_page(artist, title, run_text, category='Exhibition'):
    return (f'<html><head><title>What’s On – Museum of Chinese in America</title></head><body><h1>Museum of Chinese in America</h1>'
            f'<h1>{artist}</h1><h2>{title}</h2><p>{run_text} Category {category}</p><h2>Contact</h2></body></html>')


class MocaTest(unittest.TestCase):
    def test_reads_exhibitions_and_leaves_out_events_and_the_standing_display(self):
        home = ('<main>' + ''.join(f'<a href="/event/{s}/">x</a>' for s in ['hilda-shen', 'walking-tour', 'with-a-single-step-2']) + '</main>')
        base = 'https://www.mocanyc.org/event/'
        pages = {museum_of_chinese_in_america.HOME: home,
                 base + 'hilda-shen/': moca_page('Hilda Shen', 'Their Landscapes', 'October 22, 2026 – January 24, 2027'),
                 base + 'walking-tour/': moca_page('Public Walking Tour', 'Chinatown', 'November 21, 2026 – November 21, 2026', 'AANHPI'),
                 base + 'with-a-single-step-2/': moca_page('With a Single Step', 'Core', 'September 1, 2009 – December 31, 2028')}
        shows = run(museum_of_chinese_in_america, 'scrape_museum_of_chinese_in_america', pages)
        self.assertEqual(list(shows), ['Hilda Shen: Their Landscapes'])
        hilda = shows['Hilda Shen: Their Landscapes']
        self.assertEqual((hilda['dates']['start'], hilda['dates']['end']), (dt.date(2026, 10, 22), dt.date(2027, 1, 24)))
        self.assertEqual(hilda['links'][0]['link'], 'https://www.mocanyc.org/event/hilda-shen/')


class SikkemaTest(unittest.TestCase):
    def test_reads_the_current_shows_and_their_dotted_runs(self):
        page = ('<main><h1>CURRENT EXHIBITIONS</h1>'
                '<h2><a href="/ex20261030heidilau">HEIDI LAU<br/><em>OUROBOROS</em><br/>10.30-12.19.26</a></h2>'
                '<h2><a href="/ex20261030erin">ERIN SHIRREFF<br/>NEW WORK<br/>10.30-12.19.26</a></h2>'
                '<h2>RECENT EXHIBITIONS</h2><a href="/recent-exhibitions/x">Read more →</a></main>')
        shows = run(sikkema_malloy_jenkins, 'scrape_sikkema_malloy_jenkins', {sikkema_malloy_jenkins.PAGE_URL: page})
        self.assertEqual(sorted(shows), ['Erin Shirreff: New Work', 'Heidi Lau: Ouroboros'])
        heidi = shows['Heidi Lau: Ouroboros']
        self.assertEqual((heidi['dates']['start'], heidi['dates']['end']), (dt.date(2026, 10, 30), dt.date(2026, 12, 19)))
        self.assertEqual(heidi['links'][0]['link'], 'https://www.sikkemajenkinsco.com/ex20261030heidilau')

    def test_a_run_that_crosses_the_new_year(self):
        self.assertEqual(sikkema_malloy_jenkins.parse_run('11.20-1.16.27'), (dt.date(2026, 11, 20), dt.date(2027, 1, 16)))
        self.assertEqual(sikkema_malloy_jenkins.parse_run('Opening'), (None, None))


class RegistryTest(unittest.TestCase):
    VENUES = ['Jack Shainman Gallery', 'Museum of Chinese in America', 'Sikkema Malloy Jenkins']

    def test_each_venue_is_registered_and_has_its_data(self):
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(DOCS, 'venue_coordinates.json'), encoding='utf-8') as f:
            coordinates = json.load(f)['nyc']
        with open(os.path.join(DOCS, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['nyc']
        self.assertEqual(sorted(scrapers), sorted(venues))
        for venue in self.VENUES:
            self.assertIn(venue, scrapers)
            addresses = venues[venue] if isinstance(venues[venue], list) else [venues[venue]]
            self.assertEqual(len(coordinates[venue]), len(addresses))
        self.assertIn('Museum of Chinese in America', admission)
        self.assertEqual(sorted(label for label, _ in jack_shainman_gallery.SPACES), sorted(s['label'] for s in venues['Jack Shainman Gallery']))


if __name__ == '__main__':
    unittest.main()
