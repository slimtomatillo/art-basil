# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.mtl import (art_mur, belgo_galleries, blouin_division, cca, circa, fonderie_darling,
                          galerie_simon_blais as simon_blais, galerie_uqam, la_guilde, oboro, skol)
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


def run_pages(module, func, pages):
    """Like run(), but each URL gets its own page from `pages` (a missing URL fails to fetch)."""
    stored = []
    fetch = lambda url, headers=None: BeautifulSoup(pages[url], 'html.parser') if url in pages else None
    with mock.patch.object(module, 'fetch_and_parse', fetch), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {(e['venue'], e['name']): e for e in stored}


class CcaTest(unittest.TestCase):
    BASE = 'https://www.cca.qc.ca/en/events/'

    def show_page(self, cat, first, second, menu=''):
        return (f'<div class="menu-footer">{menu}<div class="date">Through 3 January</div></div>'
                f'<div class="c-cal-event cal-event-header"><div class="date"><span class="cat">{cat}</span>'
                f'<span class="dt">{first}</span> to <span class="dt">{second}</span></div></div>'
                f'<meta property="og:image" content="https://example.org/{first[:2].strip()}.jpg">')

    def test_dates_come_from_each_show_page_and_its_menu_adds_missing_shows(self):
        listing = ('<p>On view</p><a href="https://www.cca.qc.ca/en/events/1/reframing">Reframing the American Landscape</a>'
                   '<p>is on display in our Octagonal Gallery on 1 October 2026.</p>'
                   '<a href="https://www.cca.qc.ca/en/events/2/fortune">The fortune of the city</a>'
                   '<p>is on display in our Main Galleries until 10 January 2027.</p>')
        menu = ('<a href="/en/events/1/reframing">Reframing the American Landscape</a>'
                '<a href="/en/events/3/out-of-the-box">Out of the Box</a><a href="/en/events/4/a-talk">A talk</a>')
        pages = {
            cca.EXHIBITIONS_URL: listing,
            self.BASE + '1/reframing': self.show_page('Exhibition, Octagonal Gallery, ', '1 October 2026', '3 January 2027', menu),
            self.BASE + '2/fortune': self.show_page('Exhibition, Main Galleries, ', '21 May 2026', '28 February 2027'),
            self.BASE + '3/out-of-the-box': self.show_page('Exhibition, Octagonal Gallery, ', 'April 2027', 'March 2028'),
            self.BASE + '4/a-talk': self.show_page('Talk, ', '12 November 2026', '12 November 2026'),
        }
        events = run_pages(cca, 'scrape_cca', pages)
        venue = 'Canadian Centre for Architecture'
        self.assertEqual(sorted(n for _, n in events), ['Out of the Box', 'Reframing the American Landscape', 'The fortune of the city'])
        self.assertEqual(events[(venue, 'Reframing the American Landscape')]['dates'],
                         {'start': dt.date(2026, 10, 1), 'end': dt.date(2027, 1, 3)})
        self.assertEqual(events[(venue, 'The fortune of the city')]['dates'],
                         {'start': dt.date(2026, 5, 21), 'end': dt.date(2027, 2, 28)})
        # A month with no day runs from its first day to its last
        self.assertEqual(events[(venue, 'Out of the Box')]['dates'],
                         {'start': dt.date(2027, 4, 1), 'end': dt.date(2028, 3, 31)})


class FonderieDarlingTest(unittest.TestCase):
    def test_reads_the_dates_from_the_moment_tags(self):
        post = ('<div class="post"><div class="background"><a href="Solar-Lamentation"><img src="/en/assets/solar.jpg"></a></div>'
                '<div class="title"><h2><span class="artist">Shanie  Tomassini / </span><a href="Solar-Lamentation">Solar Lamentation</a></h2></div>'
                '<div class="text"><h3 class="date uppercase"><moment date="2026-09-17" format="DD.MM.YYYY"></moment> - '
                '<moment date="2026-11-15" format="DD.MM.YYYY"></moment></h3><h4 class="lieu">Small Gallery</h4></div></div>')
        events = run_pages(fonderie_darling, 'scrape_fonderie_darling', {fonderie_darling.LIST_URLS[0]: post})
        show = events[('Fonderie Darling', 'Shanie Tomassini: Solar Lamentation')]
        self.assertEqual(show['dates'], {'start': dt.date(2026, 9, 17), 'end': dt.date(2026, 11, 15)})
        self.assertIn({'link': 'https://fonderiedarling.org/en/Solar-Lamentation', 'description': 'Event Page'}, show['links'])
        self.assertIn({'link': 'https://fonderiedarling.org/en/assets/solar.jpg', 'description': 'Image'}, show['links'])


class ArtMurTest(unittest.TestCase):
    def test_upcoming_shows_with_italic_titles_and_their_pictures(self):
        page = ('<div class="entry-content type-page">'
                '<div class="one_half">November 14–December 19, 2026<br/>Opening reception: Saturday, November 14<br/>'
                'Karine Giboulo: <em>Retrospective and New Works</em><br/></div>'
                '<div class="one_half last"><img src="https://artmur.com/g-300x200.jpg" '
                'srcset="https://artmur.com/g-300x200.jpg 300w, https://artmur.com/g-1024x683.jpg 1024w, https://artmur.com/g.jpg 2048w"></div>'
                '<div class="clearboth"></div>'
                '<div class="one_half">November 7 to December 10, 2026<br/>Opening reception: Saturday, November 14<br/>'
                '<em>Éclosion</em> 2026<br/>Artists: Marine Bordy</div></div>')
        current = '<div class="entry-content type-page">Installation in progress</div>'
        events = run_pages(art_mur, 'scrape_art_mur', {art_mur.LIST_URLS[0]: current, art_mur.LIST_URLS[1]: page})
        giboulo = events[('Art Mûr', 'Karine Giboulo: Retrospective and New Works')]
        self.assertEqual(giboulo['dates'], {'start': dt.date(2026, 11, 14), 'end': dt.date(2026, 12, 19)})
        self.assertIn({'link': 'https://artmur.com/g-1024x683.jpg', 'description': 'Image'}, giboulo['links'])
        self.assertEqual(events[('Art Mûr', 'Éclosion 2026')]['dates'], {'start': dt.date(2026, 11, 7), 'end': dt.date(2026, 12, 10)})


class LaGuildeTest(unittest.TestCase):
    def item(self, label, headings, dates, slug):
        return (f'<div class="grid__item"><a href="/blogs/expositions/{slug}">'
                f'<img data-src="//laguilde.com/cdn/shop/files/{slug}_{{width}}x.jpg?v=1"></a><h3>{label}</h3>'
                f'<div class="rte-setting">{headings}<p>{dates}</p></div></div>')

    def test_group_and_solo_shows_and_past_ones_are_skipped(self):
        page = (self.item('Exposition Collective', '<h2>ÉCHANGES: </h2><h3>Une sélection d’oeuvres</h3>',
                          'Du 8 octobre au 14 novembre 2026', 'echanges')
                + self.item('MAry Paningajak', '<h2>Pride and joy</h2>', '30 juillet au 26 septembre 2026', 'pride')
                + self.item('Janice Toulouse', '<h2>Jiibay Spirit</h2>', '3 décembre 2026 au 30 janvier 2027', 'jiibay'))
        events = run(la_guilde, 'scrape_la_guilde', page)
        self.assertEqual(sorted(n for _, n in events), ['Janice Toulouse: Jiibay Spirit', 'Échanges: Une sélection d’oeuvres'])
        show = events[('La Guilde', 'Échanges: Une sélection d’oeuvres')]
        self.assertEqual(show['dates'], {'start': dt.date(2026, 10, 8), 'end': dt.date(2026, 11, 14)})
        self.assertIn({'link': 'https://laguilde.com/cdn/shop/files/echanges_1080x.jpg?v=1', 'description': 'Image'}, show['links'])
        self.assertIn({'link': 'https://laguilde.com/blogs/expositions/echanges', 'description': 'Event Page'}, show['links'])

    def test_a_rate_limited_fetch_is_retried_once(self):
        page = self.item('Exposition Collective', '<h2>Échanges</h2>', 'Du 8 octobre au 14 novembre 2026', 'echanges')
        replies = [None, BeautifulSoup(page, 'html.parser')]
        stored = []
        with mock.patch.object(la_guilde, 'fetch_and_parse', lambda url, headers=None: replies.pop(0)), \
                mock.patch.object(la_guilde.time, 'sleep') as sleep, \
                mock.patch.object(la_guilde, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
            la_guilde.scrape_la_guilde(env='prod')
        sleep.assert_called_once()
        self.assertEqual([e['name'] for e in stored], ['Échanges'])


class SimonBlaisTest(unittest.TestCase):
    def test_duplicates_and_offsite_shows_are_dropped(self):
        shows = blocks('Jean McEwen', 'La lumière sous les blasons', 'Nov. 4, 2026 to Dec. 19, 2026', 'View',
                       'Jean-Sébastien Denis', 'OFFSITE - HORS-GALERIE — Extensions', 'Oct. 15, 2026 to Mar. 21, 2027', 'View')
        events = run(simon_blais, 'scrape_galerie_simon_blais', shows + shows)
        self.assertEqual(list(events), [('Galerie Simon Blais', 'Jean McEwen: La lumière sous les blasons')])


if __name__ == '__main__':
    unittest.main()
