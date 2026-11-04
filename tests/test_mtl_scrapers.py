# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.mtl import belgo_galleries, blouin_division, circa, oboro, skol
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


if __name__ == '__main__':
    unittest.main()
