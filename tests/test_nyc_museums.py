# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The first batch of New York museums (WEBSITE-121, tier 1). Fixtures are trimmed copies of the sites' markup captured
# on 2026-11-13. Nothing touches the network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import (_common as nyc_common, _pages, american_folk_art_museum, bronx_museum_of_the_arts, cooper_hewitt,
                          drawing_center, international_center_of_photography, jewish_museum, museum_of_arts_and_design,
                          museum_of_the_city_of_new_york, neue_galerie_new_york, noguchi_museum)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 13)


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def run(module, scrape, pages, region='nyc'):
    """Run a scraper over {url: html}; returns {name: stored event}."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return soup(html) if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region=region)
    return {e['name']: e for e in stored}


def listing(*hrefs, extra=''):
    return '<main>' + ''.join(f'<a href="{h}">card</a>' for h in hrefs) + extra + '</main>'


def show(title, dates, site='', description=None, image='https://img.example/pic.jpg', h1=None):
    description = description or f'{title} is an exhibition of new and recent work that explores the artist\'s practice in depth.'
    return (f'<html><head><title>{title}{site}</title><meta property="og:title" content="{title}{site}">'
            f'<meta property="og:description" content="{description}"><meta property="og:image" content="{image}"></head>'
            f'<body><nav>Menu</nav><h1>{h1 or title}</h1><p>{dates}</p><p>{description}</p></body></html>')


class ShowPagesTest(unittest.TestCase):
    def test_show_links_keep_only_shows_once_without_the_section_links_or_the_listing(self):
        page = soup(listing('/exhibitions/a-show', '/exhibitions/a-show/', '/exhibitions/past', '/exhibitions/archive/', '/exhibitions/current',
                            '/exhibitions', '/exhibitions/other?x=1', 'https://elsewhere.example/exhibitions/x', '/visit',
                            '/exhibitions/past-exhibitions'))
        links = _pages.show_links(page, 'https://m.example/exhibitions/', r'^/exhibitions/[a-z0-9-]+/?$')
        self.assertEqual(links, ['https://m.example/exhibitions/a-show', 'https://m.example/exhibitions/other'])

    def test_a_show_page_gives_name_dates_description_and_picture(self):
        pages = {'u': show('Light Show', 'Oct 15, 2026 - Jan 11, 2027', ' | The Museum')}
        result = _pages.read_show('u', TODAY, fetch=lambda url: soup(pages[url]), suffix=' | The Museum')
        self.assertEqual((result['name'], result['start'], result['end']), ('Light Show', dt.date(2026, 10, 15), dt.date(2027, 1, 11)))
        self.assertTrue(result['description'].startswith('Light Show is an exhibition of new and recent work'))
        self.assertEqual(result['image'], 'https://img.example/pic.jpg')

    def test_weekday_dates_through_dates_and_a_malformed_picture(self):
        for dates, expected in (('Wed Sep 23—Sat Nov 14 2026', (dt.date(2026, 9, 23), dt.date(2026, 11, 14))),
                                ('Through Mar 7, 2027', (None, dt.date(2027, 3, 7)))):
            page = show('A Show', dates, image='https://www.icp.orgScreenshot 2026 at 12.png')
            result = _pages.read_show('u', TODAY, fetch=lambda url: soup(page))
            self.assertEqual((result['start'], result['end']), expected)
            self.assertIsNone(result['image'])

    def test_a_page_with_no_date_line_an_unreachable_page_and_a_standing_display_give_nothing(self):
        self.assertIsNone(_pages.read_show('u', TODAY, fetch=lambda url: soup(show('Permanent', 'Ongoing'))))
        self.assertIsNone(_pages.read_show('u', TODAY, fetch=lambda url: None))
        # open since 2016 with only a start date: an online display, not a show
        self.assertIsNone(_pages.read_show('u', TODAY, fetch=lambda url: soup(show('Online', 'October 19, 2016'))) )
        # a show that opened a few months ago and has no end date yet is kept
        self.assertEqual(_pages.read_show('u', TODAY, fetch=lambda url: soup(show('Recent', 'September 16, 2026')))['start'], dt.date(2026, 9, 16))

    def test_title_case_for_a_title_set_in_capitals(self):
        self.assertEqual(nyc_common.title_case('FREDERIC CHURCH IN JAMAICA'), 'Frederic Church in Jamaica')
        self.assertEqual(nyc_common.title_case("THE ARTIST'S EYE AND THE CITY"), "The Artist's Eye and the City")


class DetailPageVenuesTest(unittest.TestCase):
    """The venues read by the shared helper: each reads the shows its listing links to, with the right suffix, and
    leaves out section pages and ended shows."""

    def check(self, module, scrape, base, listings, shows, expected, suffix=''):
        pages = dict(listings)
        for path, (title, dates) in shows.items():
            pages[base + path] = show(title, dates, suffix)
        events = run(module, scrape, pages)
        self.assertEqual(sorted(events), sorted(expected))
        return events

    def test_noguchi(self):
        events = self.check(noguchi_museum, 'scrape_noguchi_museum', 'https://www.noguchi.org',
                            {noguchi_museum.LISTINGS[0]: listing('/museum/exhibitions/view/akari', '/museum/exhibitions/past/',
                                                                 '/museum/exhibitions/view/old')},
                            {'/museum/exhibitions/view/akari': ('No Ordinary Light: Akari at 75', 'November 4, 2026 – September 5, 2027'),
                             '/museum/exhibitions/view/old': ('Old Show', 'May 1, 2025 – Jan 4, 2026')},
                            ['No Ordinary Light: Akari at 75'], ' - The Noguchi Museum')
        self.assertEqual(events['No Ordinary Light: Akari at 75']['venue'], 'The Noguchi Museum')
        self.assertIn('museum', events['No Ordinary Light: Akari at 75']['tags'])

    def test_drawing_center(self):
        self.check(drawing_center, 'scrape_drawing_center', 'https://drawingcenter.org',
                   {drawing_center.LISTINGS[0]: listing('/exhibitions/form-shadow-motion', '/exhibitions/archive', '/exhibitions/old-show')},
                   {'/exhibitions/form-shadow-motion': ('Form, Shadow, Motion', 'October 23, 2026 – January 24, 2027'),
                    '/exhibitions/old-show': ('Old', 'February 20, 2026 – June 7, 2026')},
                   ['Form, Shadow, Motion'], ' | The Drawing Center')

    def test_mad_leaves_out_a_permanent_display(self):
        self.check(museum_of_arts_and_design, 'scrape_museum_of_arts_and_design', 'https://madmuseum.org',
                   {museum_of_arts_and_design.LISTINGS[0]: listing('/exhibition/nike', '/exhibition/goblets-permanent-collection')},
                   {'/exhibition/nike': ('Nike: Form Follows Motion', 'Through Mar 7, 2027'),
                    '/exhibition/goblets-permanent-collection': ('Goblets', 'Ongoing')},
                   ['Nike: Form Follows Motion'])

    def test_icp_skips_its_section_pages(self):
        self.check(international_center_of_photography, 'scrape_international_center_of_photography', 'https://www.icp.org',
                   {international_center_of_photography.LISTINGS[0]: listing('/exhibitions/laia-abril', '/exhibitions/mana-exhibitions',
                                                                             '/exhibitions/past-exhibitions', '/exhibitions/traveling-exhibitions')},
                   {'/exhibitions/laia-abril': ('Laia Abril: On Rape and Institutional Failure', 'Oct 15, 2026 - Jan 11, 2027'),
                    '/exhibitions/mana-exhibitions': ('ICP at Mana Exhibitions', 'April 28, 2019')},
                   ['Laia Abril: On Rape and Institutional Failure'])

    def test_mcny_leaves_out_an_online_exhibition_open_since_2016(self):
        self.check(museum_of_the_city_of_new_york, 'scrape_museum_of_the_city_of_new_york', 'https://www.mcny.org',
                   {museum_of_the_city_of_new_york.LISTINGS[0]: listing('/exhibition/occupied-city', '/exhibition/activist-new-york-online')},
                   {'/exhibition/occupied-city': ('The Occupied City', 'Through March 21, 2027'),
                    '/exhibition/activist-new-york-online': ('Activist New York Online', 'October 19, 2016')},
                   ['The Occupied City'])

    def test_neue_galerie_reads_current_and_upcoming(self):
        events = self.check(neue_galerie_new_york, 'scrape_neue_galerie_new_york', 'https://www.neuegalerie.org',
                            {neue_galerie_new_york.LISTINGS[0]: listing('/exhibitions/25thanniversary', '/exhibitions/1910')},
                            {'/exhibitions/25thanniversary': ('25th Anniversary Exhibition', 'Nov 12, 2026 — Jan 11, 2027'),
                             '/exhibitions/1910': ('1910: Portrait of a Year', 'Feb 18, 2027 — May 24, 2027')},
                            ['25th Anniversary Exhibition', '1910: Portrait of a Year'])
        self.assertEqual(events['1910: Portrait of a Year']['phase'], 'future')

    def test_bronx_museum_reads_both_filters_and_a_trailing_slash(self):
        self.check(bronx_museum_of_the_arts, 'scrape_bronx_museum_of_the_arts', 'https://bronxmuseum.org',
                   {bronx_museum_of_the_arts.LISTINGS[0]: listing('/exhibition/woodswoman-method/'),
                    bronx_museum_of_the_arts.LISTINGS[1]: listing('/exhibition/next-show/', '/exhibition/woodswoman-method/')},
                   {'/exhibition/woodswoman-method/': ('Saya Woolfalk: The WoodsWoman Method', 'October 9, 2026 – March 28, 2027'),
                    '/exhibition/next-show/': ('Next Show', 'January 20, 2027 – May 1, 2027')},
                   ['Saya Woolfalk: The WoodsWoman Method', 'Next Show'], ' - The Bronx Museum')

    def test_folk_art_museum(self):
        self.check(american_folk_art_museum, 'scrape_american_folk_art_museum', 'https://folkartmuseum.org',
                   {american_folk_art_museum.LISTINGS[0]: listing('/exhibitions/locating-girlhood/', '/exhibitions/upcoming/', '/exhibitions/past/'),
                    american_folk_art_museum.LISTINGS[1]: listing('/exhibitions/folk-nation/')},
                   {'/exhibitions/locating-girlhood/': ('Locating Girlhood', 'October 9, 2026–February 28, 2027'),
                    '/exhibitions/folk-nation/': ('Folk Nation', 'October 9, 2026–February 28, 2027')},
                   ['Locating Girlhood', 'Folk Nation'], ' | American Folk Art Museum')

    def test_an_unreachable_listing_stores_nothing(self):
        self.assertEqual(run(noguchi_museum, 'scrape_noguchi_museum', {}), {})


class JewishMuseumTest(unittest.TestCase):
    PAGE = ('<main>'
            '<a aria-label="On View, Modernity and Opulence: Women of the Wiener Werkstätte, Jul. 17 – Nov. 15, 2026" '
            'href="https://thejewishmuseum.org/exhibitions/women-of-the-wiener-werkstatte/"><img data-src="https://tjm.example/a.jpg" src="data:image/svg+xml,x"></a>'
            '<a aria-label="On View, Art in Focus<br>Oded Halahmy: Models in Wood, May 29, 2026 – Jan. 3, 2027" href="/exhibitions/halahmy/"></a>'
            '<a aria-label="Coming Soon, Ruth Patir: (M)otherland, Dec. 18, 2026 – Jun. 7, 2027" href="/exhibitions/patir/"></a>'
            '<a aria-label="On View, A show with no dates in the label" href="/exhibitions/nodates/"></a>'
            '<a href="/exhibitions/furnishing-american-synagogues">older show, no label</a></main>')

    def test_the_cards_aria_labels_give_title_and_dates(self):
        shows = run(jewish_museum, 'scrape_jewish_museum', {jewish_museum.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Art in Focus: Oded Halahmy: Models in Wood', 'Modernity and Opulence: Women of the Wiener Werkstätte',
                                         'Ruth Patir: (M)otherland'])
        show_ = shows['Modernity and Opulence: Women of the Wiener Werkstätte']
        self.assertEqual((show_['dates']['start'], show_['dates']['end']), (dt.date(2026, 7, 17), dt.date(2026, 11, 15)))
        self.assertEqual(show_['links'][0]['link'], 'https://thejewishmuseum.org/exhibitions/women-of-the-wiener-werkstatte/')
        self.assertEqual(show_['links'][1], {'link': 'https://tjm.example/a.jpg', 'description': 'Image'})
        self.assertEqual(shows['Ruth Patir: (M)otherland']['phase'], 'future')


class CooperHewittTest(unittest.TestCase):
    def row(self, title, status, href, text, image='https://ch.example/a.jpg'):
        return (f'<h2><span style="font-size: 32px;">{title}</span><br/> <span style="font-size: 24px;">{status}</span></h2>'
                f'<div class="row post-row previous-exhibition"><div><a href="{href}"><img src="{image}"></a></div><div><p>{text}</p></div></div>')

    def test_current_shows_are_read_and_an_ongoing_display_is_not(self):
        page = ('<div>' + self.row('FREDERIC CHURCH IN JAMAICA', 'On view THROUGH FEBRUARY 15, 2027', '/channel/frederic-church/',
                                   'Frederic Church in Jamaica centers on the artist’s rarely exhibited sketches from his 1865 travels.')
                + self.row('Design Across Time: Exploring the Smithsonian’s Design Collection', 'ONGOING', '/channel/design-across-time/', 'The first floor.')
                + self.row('The Substitute', 'On View Through February 15, 2027', '/channel/the-substitute/', 'An immersive video and sound installation.') + '</div>')
        shows = run(cooper_hewitt, 'scrape_cooper_hewitt', {cooper_hewitt.LISTINGS[0]: page, cooper_hewitt.LISTINGS[1]: '<div>no shows</div>'})
        self.assertEqual(sorted(shows), ['Frederic Church in Jamaica', 'The Substitute'])
        church = shows['Frederic Church in Jamaica']
        self.assertEqual((church['dates']['start'], church['dates']['end']), (None, dt.date(2027, 2, 15)))
        self.assertTrue(church['description'].startswith('Frederic Church in Jamaica centers'))
        self.assertEqual(church['links'][0]['link'], 'https://www.cooperhewitt.org/channel/frederic-church/')


class RegistryTest(unittest.TestCase):
    def test_every_new_york_museum_is_registered_has_an_address_and_an_admission_record(self):
        import json
        import main
        docs = os.path.join(os.path.dirname(__file__), '../docs/data')
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(docs, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(docs, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['nyc']
        self.assertEqual(sorted(scrapers), sorted(venues))
        for module in (cooper_hewitt, jewish_museum, museum_of_the_city_of_new_york, neue_galerie_new_york, noguchi_museum, drawing_center,
                       museum_of_arts_and_design, international_center_of_photography, bronx_museum_of_the_arts, american_folk_art_museum):
            self.assertIn(module.VENUE, venues)
            self.assertIn(module.VENUE, admission, f'{module.VENUE} needs an admission record')


if __name__ == '__main__':
    unittest.main()
