# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York's established galleries (WEBSITE-121, tier 3): the shared gallery reader in scrapers/nyc/galleries.py.
# Fixtures are trimmed copies of the sites' markup captured on 2026-11-14. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import _common as nyc_common, galleries
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 14)
ROOT = os.path.join(os.path.dirname(__file__), '..')


def run(venue, pages):
    """Run one gallery's scraper over {url: html}; returns {name: stored event}."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    spec = galleries.SPECS[venue]
    with mock.patch.object(galleries, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(galleries, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        galleries.scrape(spec, env='prod', region='nyc')
    return {e['name']: e for e in stored}


def page_of(venue, body):
    return {galleries.SPECS[venue].urls[0]: f'<html><body>{body}</body></html>'}


def image_of(event):
    return next((l['link'] for l in event['links'] if l['description'] == 'Image'), None)


def entry(href, *lines, image='https://static-assets.artlogic.net/w_800/exhibit-e/a/b.jpeg'):
    tags = ''.join(f'<h{n}>{line}</h{n}>' for n, line in enumerate(lines, 1))
    link = f'<a href="{href}">' if href else '<a>'
    return (f'<div class="entry">{link}<div class="thumb"><div class="image"><img src="{image}"/></div></div>'
            f'<div class="headers">{tags}</div></a></div>')


class AlternateDatesTest(unittest.TestCase):
    def test_day_first_and_dotted_runs_are_read(self):
        read = lambda text: nyc_common.parse_dates(text, TODAY)
        self.assertEqual(read('11 November 2026 - 16 January 2027'), (dt.date(2026, 11, 11), dt.date(2027, 1, 16)))
        self.assertEqual(read('5 NOVEMBER 2026 - 9 JANUARY 2027'), (dt.date(2026, 11, 5), dt.date(2027, 1, 9)))
        self.assertEqual(read('30 Oct – 19 Dec 2026'), (dt.date(2026, 10, 30), dt.date(2026, 12, 19)))
        self.assertEqual(read('29 Oct - 19 Dec 2026'), (dt.date(2026, 10, 29), dt.date(2026, 12, 19)))
        self.assertEqual(read('5-30 Nov 2026'), (dt.date(2026, 11, 5), dt.date(2026, 11, 30)))
        self.assertEqual(read('11.05–12.19.2026'), (dt.date(2026, 11, 5), dt.date(2026, 12, 19)))
        self.assertEqual(read('11.05.2026–07.04.2027'), (dt.date(2026, 11, 5), dt.date(2027, 7, 4)))

    def test_the_runs_already_read_are_unchanged_and_nonsense_is_not_a_date(self):
        self.assertEqual(nyc_common.parse_dates('Nov 6 – Dec 19, 2026', TODAY), (dt.date(2026, 11, 6), dt.date(2026, 12, 19)))
        self.assertEqual(nyc_common.parse_dates('31 Feb 2026 - 3 Mar 2026', TODAY), (None, None))
        self.assertEqual(nyc_common.parse_dates('Tuesday – Saturday', TODAY), (None, None))


class EntrySitesTest(unittest.TestCase):
    """The exhibit-e sites (Miles McEnery, Luhring Augustine, Paula Cooper, Skarstedt...): `.entry` cards with `.headers`."""

    def test_a_card_is_the_artist_and_title_with_its_dates_and_the_address_is_not_part_of_the_name(self):
        shows = run('Paula Cooper Gallery', page_of('Paula Cooper Gallery', ''.join([
            entry('/exhibitions/claes-oldenburg', 'Claes Oldenburg', 'Six Themes', '534 West 21st Street', 'November 6 – December 19, 2026'),
            entry('/exhibitions/art-is-for-the-spirit', 'Art is for the Spirit', 'Records of the Self', '521 West 21st Street', 'October 29 – December 12, 2026'),
            entry('/exhibitions/old-show', 'Old Show', '534 West 21st Street', 'May 1 – June 1, 2026')])))
        self.assertEqual(set(shows), {'Claes Oldenburg: Six Themes', 'Art is for the Spirit: Records of the Self'})
        oldenburg = shows['Claes Oldenburg: Six Themes']
        self.assertEqual(oldenburg['dates'], {'start': dt.date(2026, 11, 6), 'end': dt.date(2026, 12, 19)})
        self.assertEqual(oldenburg['locations'], ['534 West 21st Street'])
        self.assertEqual(shows['Art is for the Spirit: Records of the Self']['locations'], ['521 West 21st Street'])
        self.assertTrue(image_of(oldenburg).startswith('https://static-assets.artlogic.net/'))
        self.assertEqual(oldenburg['links'][0]['link'], 'https://www.paulacoopergallery.com/exhibitions/claes-oldenburg')

    def test_a_title_set_in_capitals_is_set_in_title_case(self):
        shows = run('Miles McEnery Gallery', page_of('Miles McEnery Gallery', entry(
            '/exhibitions/inka-essenhigh5', 'INKA ESSENHIGH', '515 WEST 22ND STREET', '5 NOVEMBER 2026 - 9 JANUARY 2027')))
        self.assertEqual(list(shows), ['Inka Essenhigh'])
        self.assertEqual(shows['Inka Essenhigh']['locations'], ['515 West 22nd Street'])

    def test_a_show_in_another_city_is_left_out(self):
        shows = run('Luhring Augustine', page_of('Luhring Augustine', ''.join([
            entry('/exhibitions/jason-moran3', 'Jason Moran', 'STACKS', 'November 6 – December 19, 2026'),
            entry('/exhibitions/maison-leleu', 'Maison Leleu x Luhring Augustine',
                  'Maison Leleu Showroom, 15 rue des Saints Pères, Paris', 'October 21, 2026 – February 26, 2027')])))
        self.assertEqual(list(shows), ['Jason Moran: Stacks'])

    def test_a_group_show_is_named_by_its_title_not_its_list_of_artists(self):
        shows = run('Skarstedt', page_of('Skarstedt', ''.join([
            '<div class="entry half not-clickable"><div class="thumb"></div><div class="list-detail-title"> New York - Upper East Side </div>'
            '<div class="headers"><h1>Dark Comedy</h1><h2>Robert Gober, Jenny Holzer, Mike Kelley, Martin Kippenberger, Jeff Koons</h2>'
            '<h3>November 12 – December 19, 2026</h3></div></div>',
            '<div class="entry half"><a href="/exhibitions/eric-fischl"><div class="thumb"></div><div class="list-detail-title"> Chelsea </div>'
            '<div class="headers"><h1>Eric Fischl: In Pursuit of Pleasure</h1><h3>November 12 – December 19, 2026</h3></div></a></div>'])))
        self.assertEqual(set(shows), {'Dark Comedy', 'Eric Fischl: In Pursuit of Pleasure'})
        self.assertEqual(shows['Dark Comedy']['locations'], ['Upper East Side'])
        self.assertEqual(shows['Eric Fischl: In Pursuit of Pleasure']['locations'], ['Chelsea'])
        # a card that is not a link goes to the listing
        self.assertEqual(shows['Dark Comedy']['links'][0]['link'], 'https://www.skarstedt.com/exhibitions')

    def test_past_cards_with_no_text_are_ignored(self):
        shows = run('Petzel Gallery', page_of('Petzel Gallery', entry('/exhibitions/tschabalala-self2', 'Tschabalala Self', 'Tools of Worship',
                                                                      '520 W 25th Street', 'November 5, 2026 – January 30, 2027')
                                                + '<div class="entry"><a href="/exhibitions/emily-mae-smith3"><div class="thumb"></div></a></div>'))
        self.assertEqual(list(shows), ['Tschabalala Self: Tools of Worship'])


def card(href, *lines):
    return f'<div class="card"><a href="{href}" class="more">Read more</a>' + ''.join(f'<p>{line}</p>' for line in lines) + '</div>'


class TextCardSitesTest(unittest.TestCase):
    """Sites that list a show as its lines of text and a "Read more" link (Anton Kern, Jane Lombard, Yossi Milo, ACA)."""

    def test_a_card_is_read_by_its_lines_and_the_description_below_the_dates_is_ignored(self):
        listing = card('/exhibitions/534-ellen-gronemeyer-deja-vu/', 'Ellen Gronemeyer: DÉJÀ VU', 'November 11, 2026 - January 16, 2027',
                       'Anton Kern Gallery is pleased to announce Ellen Gronemeyer’s third solo exhibition in New York.')
        listing += card('/exhibitions/533-old/', 'Old Show', 'July 7 - August 14, 2026', 'A description.')
        shows = run('Anton Kern Gallery', page_of('Anton Kern Gallery', listing))
        self.assertEqual(list(shows), ['Ellen Gronemeyer: DÉJÀ VU'])
        self.assertEqual(shows['Ellen Gronemeyer: DÉJÀ VU']['locations'], ['16 East 55th Street'])

    def test_a_show_in_the_window_space_is_stored_at_the_window(self):
        listing = card('/exhibitions/540-window/', 'Someone: Window Show', 'WINDOW, 91 Walker Street New York, NY (corner of Walker)',
                       'November 20, 2026 - January 16, 2027', 'Text.')
        shows = run('Anton Kern Gallery', page_of('Anton Kern Gallery', listing))
        self.assertEqual(list(shows), ['Someone: Window Show'])
        self.assertEqual(shows['Someone: Window Show']['locations'], ['WINDOW'])

    def test_a_project_space_label_is_not_part_of_the_name(self):
        listing = card('/exhibitions/96-jlg-projects-rachael-anderson/', 'JLG Projects', 'Rachael Catharine Anderson: Hidden Peril',
                       'October 30 - December 12, 2026', 'Text.')
        shows = run('Jane Lombard Gallery', page_of('Jane Lombard Gallery', listing))
        self.assertEqual(list(shows), ['Rachael Catharine Anderson: Hidden Peril'])

    def test_a_link_to_a_shows_installation_views_goes_to_the_show(self):
        listing = card('/exhibitions/201-ibrahim-said-shaping-time/installation_shots/', 'Ibrahim Said:', 'Shaping Time',
                       "Artist's Reception: October 22, 6-8 PM", 'October 22, 2026 - January 9, 2027')
        shows = run('Yossi Milo Gallery', page_of('Yossi Milo Gallery', listing))
        self.assertEqual(list(shows), ['Ibrahim Said: Shaping Time'])
        self.assertEqual(shows['Ibrahim Said: Shaping Time']['links'][0]['link'],
                         'https://www.yossimilo.com/exhibitions/201-ibrahim-said-shaping-time/')


class CitySitesTest(unittest.TestCase):
    """Galleries that show in several cities name the city on each card: only New York's are kept."""

    def test_lisson_keeps_the_new_york_cards_only(self):
        def lisson(href, *lines):
            return f'<div><a class="cover" href="{href}"></a>' + ''.join(f'<h3>{line}</h3>' for line in lines) + '</div>'
        shows = run('Lisson Gallery', page_of('Lisson Gallery', ''.join([
            lisson('/exhibitions/yu-hong-lisson-new-york', 'New York', 'Yu Hong', 'Field of Asura', '4 November 2026 – 23 January 2027'),
            lisson('/exhibitions/will-return', 'Shanghai', 'Ceal Floyer', 'Will Return', '12 September 2026 – 28 October 2028'),
            lisson('/exhibitions/venice', 'Lisson Artists in Venice 2026', '9 May – 22 November 2026')])))
        self.assertEqual(list(shows), ['Yu Hong: Field of Asura'])

    def test_marian_goodman_keeps_the_new_york_cards_only(self):
        def card_(*lines):
            return '<div><a href="/exhibitions/1-x/"></a>' + ''.join(f'<p>{line}</p>' for line in lines) + '</div>'
        shows = run('Marian Goodman Gallery', page_of('Marian Goodman Gallery', ''.join([
            card_('Paris', 'Tacita Dean and Bruce Nauman', '19 October - 19 December 2026'),
            card_('New York', 'Nairy Baghramian', 'nameless', '11 November 2026 - 16 January 2027')])))
        self.assertEqual(list(shows), ['Nairy Baghramian: nameless'])

    def test_a_card_that_does_not_name_new_york_is_left_out_when_the_site_names_every_city(self):
        shows = run('Lehmann Maupin', page_of('Lehmann Maupin', '<div><a href="/exhibitions/a">a</a><p>Kim Yun Shin: In the Continuum</p><p>Seoul</p>'
                                              '<p>Nov 5–Dec 24, 2026</p></div>'))
        self.assertEqual(shows, {})


class OtherLayoutsTest(unittest.TestCase):
    def test_bortolami_reads_the_title_and_artist_at_39_walker_and_leaves_offsite_shows(self):
        def show(href, title, artist, dates, place):
            return f'<a href="{href}"><h3><em>{title}</em></h3><h4>{artist}</h4><h4>{dates}</h4><h5>{place}</h5></a>'
        shows = run('Bortolami', page_of('Bortolami', ''.join([
            show('/exhibitions/35', '#35', 'Rebecca Morris', '30 Oct – 19 Dec 2026', '39 Walker'),
            show('/exhibitions/as-a-moment', 'As a moment and as an accumulation', 'Maki Katayama, Hikari Ono', '30 Oct – 19 Dec 2026',
                 'The Upstairs at 39 Walker'),
            show('/exhibitions/imaginary-engine', 'Imaginary Engine', 'Madeline Hollander', '17 Oct 2026 – 7 Mar 2027', 'Le Large')])))
        self.assertEqual(set(shows), {'Rebecca Morris: #35', 'As a moment and as an accumulation: Maki Katayama, Hikari Ono'})

    def test_salon_94_reads_its_repeated_card_and_keeps_only_its_own_address(self):
        def show(href, *parts):
            return f'<a href="{href}">' + ''.join(f'<p>{p}</p>' for p in parts) + '</a>'
        shows = run('Salon 94', page_of('Salon 94', ''.join([
            show('/exhibitions/karon-davis-wishful-thinking', '11.05–12.19.2026', 'Wishful Thinking', '3 E 89th Street',
                 '11.05–12.19.2026', '3 E 89th Street', 'Karon Davis', 'Wishful Thinking', 'Karon Davis'),
            show('/exhibitions/not-my-circus', '11.05.2026–07.04.2027', 'Not My Circus', 'Seattle Art Museum', 'Karon Davis')])))
        self.assertEqual(list(shows), ['Karon Davis: Wishful Thinking'])
        self.assertEqual(shows['Karon Davis: Wishful Thinking']['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 12, 19)})

    def test_norr_cohan_stores_the_show_at_both_walker_street_spaces(self):
        listing = ('<a href="/gallery-exhibitions/tuan-andrew-nguyen4"><div>Tuan Andrew Nguyen</div><span>Sacred Forest / Rù\'ng Thiêng</span>'
                   '<span>Gallery Exhibition at 48 and 52 Walker Street</span><span>October 30 - December 19, 2026</span></a>'
                   '<a href="/institutions/naudline-pierre-at-the-ica-miami"><div>Naudline Pierre at the ICA Miami</div><span>Miami, FL</span>'
                   '<span>November 11, 2026 - July 27, 2027</span></a>')
        shows = run('Norr Cohan', page_of('Norr Cohan', listing))
        self.assertEqual(list(shows), ["Tuan Andrew Nguyen: Sacred Forest / Rù'ng Thiêng"])
        self.assertEqual(shows["Tuan Andrew Nguyen: Sacred Forest / Rù'ng Thiêng"]['locations'], ['48 Walker Street', '52 Walker Street'])

    def test_galerie_lelong_keeps_its_own_shows_and_not_museum_or_other_gallery_shows(self):
        def show(*lines):
            return '<div><a href="/exhibitions/280-x/">View More</a>' + ''.join(f'<p>{line}</p>' for line in lines) + '</div>'
        shows = run('Galerie Lelong & Co.', page_of('Galerie Lelong & Co.', ''.join([
            show('Mildred Thompson: Cosmos Calling', '29 Oct - 19 Dec 2026', 'Galerie Lelong Exhibitions'),
            show('Jaume Plensa: Remote, Serene, Ethereal', 'GRAY New York', '23 Sep - 19 Dec 2026', 'Galerie Lelong Exhibitions'),
            show('Alfredo Jaar', 'Pinacoteca do Ceará, Fortaleza, Brazil', '15 Aug 2026 - 7 Mar 2027', 'Museum & Public Exhibitions')])))
        self.assertEqual(list(shows), ['Mildred Thompson: Cosmos Calling'])


class VenueDataTest(unittest.TestCase):
    def test_every_gallery_has_an_address_a_registered_scraper_and_coordinates_in_the_right_places(self):
        with open(os.path.join(ROOT, 'docs', 'data', 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(ROOT, 'docs', 'data', 'venue_coordinates.json'), encoding='utf-8') as f:
            coordinates = json.load(f)['nyc']
        for venue, spec in galleries.SPECS.items():
            self.assertIn(venue, venues)
            self.assertIn(venue, coordinates)
            count = len(venues[venue]) if isinstance(venues[venue], list) else 1
            self.assertEqual(len(coordinates[venue]), count, venue)
            self.assertEqual(count, len(spec.spaces), venue)
            for _label, _address, pattern in spec.spaces:
                self.assertTrue(pattern)

    def test_a_scraper_exists_for_every_gallery(self):
        self.assertEqual(set(galleries.scrapers()), set(galleries.SPECS))


if __name__ == '__main__':
    unittest.main()
