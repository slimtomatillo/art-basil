# Run with the project's Python: python -m unittest discover -s tests
#
# WEBSITE-129: three venues that "stored no events" because their pages changed shape, each with a show that was on the
# site: Headlands (an ongoing show's listing has no dates, they are on its own page), Arsenal art contemporain (one show
# says "A venir" without the accent) and El Museo del Barrio (on-view and upcoming shows are div.exhcard cards, not h3
# cards). Fixtures are trimmed copies of the markup the sites served on 2026-11-18. Nothing touches the network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.mtl import arsenal_art_contemporain as arsenal
from scrapers.nyc import el_museo_del_barrio
from scrapers.sf import headlands_center_for_the_arts as headlands
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 18)


def run(module, scrape, region, pages):
    """Run a scraper on saved pages ({url: html}); returns the stored events by name."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(module, 'process_event', side_effect=lambda d, r: stored.append(d), create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region=region)
    return {e['name']: e for e in stored}


def span(event):
    return event['dates']['start'], event['dates']['end']


# --- Headlands ---------------------------------------------------------------------------------------------------

WALL_SPACE_URL = 'https://www.headlands.org/event/wall-space-2026-eileen-myles/'


def listing_block(kind, title, date_text, url, ongoing=False):
    return (f'<div class="listing-block--event" data-event-type="{kind}"' + (' data-is-ongoing="1"' if ongoing else '') + '>'
            f'<a class="screen-link" href="{url}"><span class="visually-hidden">View {title}</span></a>'
            f'<div class="content"><div class="event-type">{kind}</div><h2 class="event-title">{title}</h2>'
            f'<div class="event-date">{date_text}</div></div></div>')


# An ongoing show says where it is in the date line; its dates are on its page, in the "When" line
WHATS_ON = ('<html><body>'
            + listing_block('public-dinner', '2026 Monthly Supper Series', 'Headlands, The Mess Hall', 'https://www.headlands.org/event/supper/', True)
            + listing_block('exhibition', 'Wall Space 2026: Eileen Myles', 'Headlands, The Commons', WALL_SPACE_URL, True)
            + listing_block('exhibition', 'Wall Space 2026: Eileen Myles', 'Headlands, The Commons', WALL_SPACE_URL, True)   # listed twice
            + listing_block('permanent-installation', 'The Latrine', 'Headlands, Building 944', 'https://www.headlands.org/event/the-latrine/', True)
            + '</body></html>')
WALL_SPACE_PAGE = ('<html><body><h1>Wall Space 2026: Eileen Myles</h1>'
                   '<div class="meta-info d-flex justify-content-between"><div class="label"><strong>Where</strong></div><div class="value">The Commons</div></div>'
                   '<div class="meta-info d-flex justify-content-between"><div class="label"><strong>When</strong></div>'
                   '<div class="value">August 16, 2026 – December 31, 2026</div></div></body></html>')


class HeadlandsTest(unittest.TestCase):
    def test_page_when_reads_the_when_line_and_nothing_else(self):
        self.assertEqual(headlands.page_when(BeautifulSoup(WALL_SPACE_PAGE, 'html.parser')), 'August 16, 2026 – December 31, 2026')
        self.assertIsNone(headlands.page_when(BeautifulSoup('<html><body><h1>No dates</h1></body></html>', 'html.parser')))

    def test_a_show_with_no_dates_in_the_listing_takes_them_from_its_page(self):
        shows = run(headlands, 'scrape_headlands_center_for_the_arts', 'sf', {headlands.WHATS_ON_URL: WHATS_ON, WALL_SPACE_URL: WALL_SPACE_PAGE})
        self.assertEqual(list(shows), ['Wall Space 2026: Eileen Myles'])                  # dinners and permanent installations are left out
        show = shows['Wall Space 2026: Eileen Myles']
        self.assertEqual(span(show), (dt.date(2026, 8, 16), dt.date(2026, 12, 31)))
        self.assertEqual(show['phase'], 'current')
        self.assertEqual(show['links'][0]['link'], WALL_SPACE_URL)

    def test_a_listing_that_has_its_dates_does_not_fetch_the_page(self):
        listing = '<html><body>' + listing_block('installation', 'Project Space: A & B', 'Nov 6–Dec 13, Thursday–Sunday, 12–5PM', 'https://www.headlands.org/event/a-b/') + '</body></html>'
        pages = {headlands.WHATS_ON_URL: listing}                                          # no page for the show: it must not be asked for
        shows = run(headlands, 'scrape_headlands_center_for_the_arts', 'sf', pages)
        self.assertEqual(span(shows['Project Space: A & B']), (dt.date(2026, 11, 6), dt.date(2026, 12, 13)))

    def test_a_show_whose_page_has_no_dates_is_left_out(self):
        shows = run(headlands, 'scrape_headlands_center_for_the_arts', 'sf',
                    {headlands.WHATS_ON_URL: WHATS_ON, WALL_SPACE_URL: '<html><body><h1>Wall Space</h1></body></html>'})
        self.assertEqual(shows, {})


# --- Arsenal art contemporain ------------------------------------------------------------------------------------

LIST_PAGE = ('<html><body><a href="/montreal/expositions/details/kimdorland2026">Kim Dorland</a>'
             '<a href="/montreal/expositions/details/bladerunner">Blade Runner</a>'
             '<a href="/montreal/expositions/details/old-show">Old</a><h2>PASSÉES</h2>'
             '<a href="/montreal/expositions/details/way-back">Way back</a></body></html>')


def detail_page(lines):
    return '<html><body>' + ''.join(f'<p>{line}</p>' for line in lines) + '</body></html>'


KIM_DORLAND = detail_page(['Billetterie', 'Kim Dorland - Retrospective', 'A venir', '27 sept.', 'Écrit par', 'Arsenal art contemporain',
                           'Billetterie', '4 décembre 2026 - 10 janvier 2027', 'Durant la période des fêtes, Arsenal art contemporain prépare une exposition.'])
BLADE_RUNNER = detail_page(['Billetterie', 'Blade Runner: l’expérience immersive', 'A venir', '1 août', 'Écrit par', 'Arsenal art contemporain',
                            'À partir du mois de mars 2027.', 'Entrez dans Los Angeles, en 2049.'])
OLD_SHOW = detail_page(['Billetterie', 'An Old Show', 'Passée', '1 mars', 'Écrit par', 'Arsenal art contemporain', '1 mars 2026 - 1 avril 2026'])


class ArsenalTest(unittest.TestCase):
    def test_the_state_line_is_found_with_or_without_the_accent(self):
        for text, state in [('À venir', 'a venir'), ('A venir', 'a venir'), ('En cours', 'en cours'), ('Passée', 'passee'), ('Passee', 'passee'),
                            ('Biennale ELEKTRA', None), ('', None), (None, None)]:
            self.assertEqual(arsenal._state(text), state, text)

    def test_an_upcoming_show_written_without_the_accent_is_kept_and_one_with_no_run_is_not(self):
        base = 'https://www.arsenalcontemporary.com'
        pages = {arsenal.LIST_URL: LIST_PAGE, base + '/montreal/expositions/details/kimdorland2026': KIM_DORLAND,
                 base + '/montreal/expositions/details/bladerunner': BLADE_RUNNER, base + '/montreal/expositions/details/old-show': OLD_SHOW}
        shows = run(arsenal, 'scrape_arsenal_art_contemporain', 'mtl', pages)
        self.assertEqual(list(shows), ['Kim Dorland - Retrospective'])                    # Blade Runner only says "from March 2027"; Passée is past
        self.assertEqual(span(shows['Kim Dorland - Retrospective']), (dt.date(2026, 12, 4), dt.date(2027, 1, 10)))
        self.assertEqual(shows['Kim Dorland - Retrospective']['phase'], 'future')


# --- El Museo del Barrio -----------------------------------------------------------------------------------------

ON_VIEW_CARD = ('<div class="exhcard"><a href="https://elmuseo.org/exhibition/teddy-sandoval-and-the-butch-gardens-school-of-art/">'
                '<div class="exh-img"><img decoding="async" src="https://elmuseo.org/wp-content/uploads/2026/06/teddy-sandoval-web-banner-dark-on-light-no-date-1-1024x512.jpg" class="deskimg" alt="Banner for Teddy Sandoval">'
                '<img decoding="async" src="https://elmuseo.org/wp-content/uploads/2026/06/teddy-sandoval-web-banner-dark-on-light-no-date-thumb.png" class="mobimg" alt="mobile"></div>'
                '<div class="exfechas">September 10, 2026 – January 10, 2027</div>'
                '<div class="exh-1col-name">Teddy Sandoval and the Butch Gardens School of Art</div></a></div>')
UPCOMING_CARD = ('<div class="exhcard"> .upcoming{display:inline-block!important;} <a href="https://elmuseo.org/exhibition/a-mano-art-and-craft-from-the-permanent-collection/">'
                 '<div class="exh-img"><img decoding="async" src="https://elmuseo.org/wp-content/uploads/2026/11/AM26_WebsiteBannerMobile-720-1.png" alt="Banner for A Mano"></div>'
                 '<div class="exfechas">January 6 - April 25, 2027</div>'
                 '<div class="exh-1col-name">A Mano: Art and Craft from the Permanent Collection</div></a></div>')
PAST_CARD = ('<div><div><div><a href="https://elmuseo.org/exhibition/sophie-rivera-double-exposures/"><img src="https://elmuseo.org/wp-content/uploads/2025/11/SophieRivera-self-portrait-m.jpg" alt="x"></a></div></div>'
             '<div><div><div>April 23 – August 2, 2026</div></div></div>'
             '<div><div><h3><a href="https://elmuseo.org/exhibition/sophie-rivera-double-exposures/">Sophie Rivera: Double Exposures</a></h3></div></div></div>')


class ElMuseoCardsTest(unittest.TestCase):
    def test_on_view_and_upcoming_cards_are_read_and_the_past_ones_dropped(self):
        html = f'<main><h2>On View</h2>{ON_VIEW_CARD}<h2>Upcoming</h2>{UPCOMING_CARD}<h2>PAST EXHIBITIONS</h2>{PAST_CARD}</main>'
        shows = run(el_museo_del_barrio, 'scrape_el_museo_del_barrio', 'nyc', {el_museo_del_barrio.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['A Mano: Art and Craft from the Permanent Collection', 'Teddy Sandoval and the Butch Gardens School of Art'])
        teddy = shows['Teddy Sandoval and the Butch Gardens School of Art']
        self.assertEqual(span(teddy), (dt.date(2026, 9, 10), dt.date(2027, 1, 10)))
        self.assertEqual(teddy['phase'], 'current')
        self.assertEqual(teddy['links'][0]['link'], 'https://elmuseo.org/exhibition/teddy-sandoval-and-the-butch-gardens-school-of-art/')
        self.assertTrue(any(link['link'].endswith('teddy-sandoval-web-banner-dark-on-light-no-date-1-1024x512.jpg') for link in teddy['links']))
        a_mano = shows['A Mano: Art and Craft from the Permanent Collection']
        self.assertEqual(span(a_mano), (dt.date(2027, 1, 6), dt.date(2027, 4, 25)))
        self.assertEqual(a_mano['phase'], 'future')

    def test_the_past_section_alone_stores_nothing(self):
        html = f'<main><h2>On View</h2><h2>Upcoming</h2><h2>PAST EXHIBITIONS</h2>{PAST_CARD}</main>'
        self.assertEqual(run(el_museo_del_barrio, 'scrape_el_museo_del_barrio', 'nyc', {el_museo_del_barrio.PAGE_URL: html}), {})


if __name__ == '__main__':
    unittest.main()
