# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.mtl import (belgo_galleries, blouin_division, cca, circa, galerie_simon_blais as simon_blais,
                          galerie_uqam, oboro, skol)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 4)


def run(module, func, html):
    """Run one scraper over a page; returns {(venue, name): stored event}."""
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(f'<main>{html}</main>', 'html.parser')), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {(e['venue'], e['name']): e for e in stored}


def blocks(*lines):
    return ''.join(f'<p>{line}</p>' for line in lines)


class BelgoTest(unittest.TestCase):
    PAGE = blocks(
        'Galerie B-312', 'Local :', '403', 'Centre d’artistes', 'Heures d’ouverture :', 'Mardi au samedi, 12h-17h',
        'Exposition :', 'Gambits', 'Brendan Flanagan', 'Dates :', '5 novembre au 12 décembre', '2026',
        'Vernissage : jeudi 5 novembre de 17h à 20h',
        'Éclats Art contemmporain', 'Local :', '521', 'Galerie d’art', 'Heures d’ouverture :', 'Lun.-ven., 11h30-16h',
        'Exposition :', 'Lignes de Rencontres', 'Sonia Roseval et Won Ch. Kimetarx', 'Dates :', '15 octobre au 14 novembre', '2026',
        'Atelier Suárez', 'Local :', '325', 'Atelier d’artiste', 'Luis Fernando Suárez', 'Heures d’ouverture :', '(Ouvert sur rendez-vous)',
        'Galerie INGANG', 'Local :', '427', 'Galerie d’art', 'Heures d’ouverture :', 'Samedi, 12h-16h',
        'Exposition :', 'BRAQUAGE DES CODES : Quand l’art subvertit les règles', 'Exposition :', 'vidéoludique', 'Pikanoa',
        '5 novembre au 12 décembre', ', 2026', 'Le Belgo —', '40 ans')

    def test_each_tenant_is_its_own_venue(self):
        events = run(belgo_galleries, 'scrape_belgo_galleries', self.PAGE)
        self.assertEqual(sorted(v for v, _ in events), ['Galerie B-312', 'Galerie INGANG', 'Éclats Art contemporain'])
        show = events[('Galerie B-312', 'Brendan Flanagan: Gambits')]
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 12, 12)})
        self.assertEqual(show['phase'], 'future')

    def test_a_group_show_keeps_just_its_title_and_unlabelled_blocks_are_read(self):
        events = run(belgo_galleries, 'scrape_belgo_galleries', self.PAGE)
        self.assertIn(('Éclats Art contemporain', 'Lignes de Rencontres'), events)
        self.assertIn(('Galerie INGANG', 'Pikanoa: BRAQUAGE DES CODES : Quand l’art subvertit les règles vidéoludique'), events)


    def test_each_show_links_to_its_own_page_when_the_tenant_has_one(self):
        page = ('<h3 class="t TitleName"><a href="https://b312.ca/">Galerie B-312</a></h3><a href="https://b312.ca/programmation/gambits"></a>'
                + blocks('Local :', '403', 'Centre d’artistes', 'Heures d’ouverture :', 'Mardi au samedi, 12h-17h',
                         'Exposition :', 'Gambits', 'Dates :', '5 novembre au 12 décembre', '2026')
                + '<h3 class="t TitleName"><a href="https://kubart.example/">Galerie Kub’Art</a></h3><a href="https://www.instagram.com/kubart/"></a>'
                + blocks('Local :', '411', 'Galerie d’art', 'Heures d’ouverture :', '(Ouvert sur rendez-vous)',
                         'Exposition inaugurale', '12 novembre au 11 décembre'))
        events = run(belgo_galleries, 'scrape_belgo_galleries', page)
        links = {v: [l['link'] for l in e['links'] if l['description'] == 'Event Page'][0] for (v, _), e in events.items()}
        self.assertEqual(links['Galerie B-312'], 'https://b312.ca/programmation/gambits')
        self.assertEqual(links['Galerie Kub’Art'], 'https://kubart.example/')


class OboroTest(unittest.TestCase):
    def test_group_and_solo_shows(self):
        page = blocks('Expositions', 'En cours', '2 oct', 'au', '28 nov 2026', 'Le jaguar et l\'oiseau écarlate', 'Exposition collective',
                      'Commissaire : Rodrigo D’Alcântara', 'À venir', '20', 'au', '28 nov 2026', 'Karl Lemieux', 'Plateformes',
                      'Événements', 'En cours', '18 août', 'au', '28 nov 2026', 'Rentrée culturelle 2026')
        events = run(oboro, 'scrape_oboro', page)
        self.assertEqual(sorted(n for _, n in events), ['Karl Lemieux: Plateformes', 'Le jaguar et l\'oiseau écarlate'])
        self.assertEqual(events[('OBORO', 'Karl Lemieux: Plateformes')]['dates'], {'start': dt.date(2026, 11, 20), 'end': dt.date(2026, 11, 28)})


class SkolTest(unittest.TestCase):
    def test_title_above_a_french_date_range(self):
        page = blocks('© 2026 Centre des arts actuels SKOL', 'Expositions', 'Fait maison : histoires badass',
                      'Exposition individuelle nourrie de gestes collectifs Du 10 septembre au 28 novembre 2026 Rencontre avec l’artiste',
                      'Essaimer Inside Out', 'Exposition collective du 2 juillet au 29 août 2026')
        events = run(skol, 'scrape_skol', page)
        self.assertEqual(list(events), [('SKOL', 'Fait maison : histoires badass')])
        self.assertEqual(events[('SKOL', 'Fait maison : histoires badass')]['dates'], {'start': dt.date(2026, 9, 10), 'end': dt.date(2026, 11, 28)})


class CircaTest(unittest.TestCase):
    def test_a_show_listed_twice_is_stored_once_with_its_artist(self):
        page = blocks('Années', 'Excavation et ablution', 'Janeva L. Fauve', 'Du 5 novembre au 19 décembre 2026',
                      'Excavation et ablution', 'Janeva L. Fauve', 'Du 5 novembre au 19 décembre 2026', 'Soutenir CIRCA')
        events = run(circa, 'scrape_circa', page)
        self.assertEqual(list(events), [('CIRCA art actuel', 'Janeva L. Fauve: Excavation et ablution')])


class BlouinDivisionTest(unittest.TestCase):
    @staticmethod
    def item(heading, subtitle, date):
        return (f'<li><a href="/en/exhibitions/1/overview/"><div class="content"><h2>{heading}</h2>'
                f'<span class="subtitle">{subtitle}</span><span class="date">{date}</span></div></a></li>')

    def test_only_montreal_shows_are_kept(self):
        page = '<ul>' + self.item('2026 | Caroline Monnet | MONTRÉAL', 'Kwìngwan', 'Sep 10 - Nov 7, 2026') \
            + self.item('2026 | Camille Charbonneau | MONTRÉAL (PROJECT SPACE)', 'Unmoored', 'Sep 10 - Nov 7, 2026') \
            + self.item('2026 | Sean Weisgerber | TORONTO', 'Long Live the New', 'Oct 30 - Dec 19, 2026') + '</ul>'
        events = run(blouin_division, 'scrape_blouin_division', page)
        self.assertEqual(sorted(n for _, n in events), ['Camille Charbonneau: Unmoored', 'Caroline Monnet: Kwìngwan'])


def run_pages(module, func, pages):
    """Like run(), for a scraper that reads several pages: pages maps each URL to its HTML."""
    stored = []

    def fetch(url, headers=None):
        return BeautifulSoup(f'<main>{pages[url]}</main>', 'html.parser') if url in pages else None

    with mock.patch.object(module, 'fetch_and_parse', fetch), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {(e['venue'], e['name']): e for e in stored}


class UqamTest(unittest.TestCase):
    PAGES = {
        'https://galerie.uqam.ca/en/statut/current/': '<a href="https://galerie.uqam.ca/en/expositions/touring/">Emmanuelle Léonard. Deployment</a>'
                                                       '<a href="https://galerie.uqam.ca/en/expositions/virtual/">Virtual exhibition: Agora</a>',
        'https://galerie.uqam.ca/en/statut/upcoming/': '<a href="https://galerie.uqam.ca/en/expositions/rift/">Anahita Norouzi. Rift</a>'
                                                        '<a href="https://galerie.uqam.ca/en/expositions/later/">Passage à découvert 2027</a>',
        'https://galerie.uqam.ca/en/expositions/touring/': blocks('Artist:', 'Emmanuelle Léonard', 'Confederation Centre, Charlottetown',
                                                                 'September 19, 2026 - January 10, 2027', 'Deployment'),
        'https://galerie.uqam.ca/en/expositions/rift/': blocks('Artist:', 'Anahita Norouzi', 'November 6, 2026 - January 16, 2027', 'Opening:'),
        'https://galerie.uqam.ca/en/expositions/later/': blocks('Artist:', 'Someone', 'Opening:'),
    }

    def test_only_gallery_shows_with_dates_are_kept(self):
        events = run_pages(galerie_uqam, 'scrape_galerie_uqam', self.PAGES)
        self.assertEqual(list(events), [("Galerie de l'UQAM", 'Anahita Norouzi. Rift')])
        self.assertEqual(events[("Galerie de l'UQAM", 'Anahita Norouzi. Rift')]['dates'],
                         {'start': dt.date(2026, 11, 6), 'end': dt.date(2027, 1, 16)})


class CcaTest(unittest.TestCase):
    def test_end_dates_and_start_dates(self):
        page = blocks('On view', 'The fortune of the city is that it has never been perfect',
                      'is on display in our Main Galleries until 10 January 2027.', 'Upcoming', 'LAWS',
                      'opens in our Main Galleries on 18 March 2027.', 'We see each exhibition as an opportunity')
        events = run(cca, 'scrape_cca', page)
        self.assertEqual(events[('Canadian Centre for Architecture', 'The fortune of the city is that it has never been perfect')]['dates'],
                         {'start': None, 'end': dt.date(2027, 1, 10)})
        self.assertEqual(events[('Canadian Centre for Architecture', 'LAWS')]['dates'], {'start': dt.date(2027, 3, 18), 'end': None})


class SimonBlaisTest(unittest.TestCase):
    @staticmethod
    def row(artist, title, dates, href, image):
        return (f'<div class="row"><div class="col-6"><a href="{href}"><img src="{image}"/></a></div><div class="col-6">'
                f'<div class="expo_summary_text"><h3 class="expo_summary_artists">{artist}</h3>'
                f'<div class="expo_summary_name">{title}</div><div class="expo_summary_dates">{dates}</div>'
                f'<a class="btn" href="{href}">View</a></div></div></div>')

    def test_duplicates_and_offsite_shows_are_dropped_and_the_row_picture_is_kept(self):
        shows = self.row('Jean McEwen', 'La lumière sous les blasons', 'Nov. 4, 2026 to Dec. 19, 2026', '/en/expos/mcewen', '/media/mcewen.jpg') \
            + self.row('Jean-Sébastien Denis', 'OFFSITE - HORS-GALERIE — Extensions', 'Oct. 15, 2026 to Mar. 21, 2027', '/en/expos/denis', '/media/denis.jpg')
        events = run(simon_blais, 'scrape_galerie_simon_blais', shows + shows)
        self.assertEqual(list(events), [('Galerie Simon Blais', 'Jean McEwen: La lumière sous les blasons')])
        links = events[('Galerie Simon Blais', 'Jean McEwen: La lumière sous les blasons')]['links']
        self.assertIn({'link': 'https://galeriesimonblais.com/media/mcewen.jpg', 'description': 'Image'}, links)


if __name__ == '__main__':
    unittest.main()
