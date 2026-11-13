# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
import urllib.parse
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import (eighteenth_street_arts_center as eighteenth, fowler_museum_at_ucla as fowler,
                         japanese_american_national_museum as janm, skirball_cultural_center as skirball,
                         vincent_price_art_museum as vpam, wende_museum as wende,
                         california_african_american_museum as caam, ica_la, molaa, _gallery,
                         anat_ebgi_gallery as anat_ebgi, charlie_james_gallery as charlie_james,
                         commonwealth_and_council as commonwealth, david_kordansky_gallery as kordansky,
                         gagosian_beverly_hills as gagosian, night_gallery)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 4)


def run(module, func, html):
    """Run one scraper over a page of text blocks (one line each); returns {name: stored event}."""
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', lambda url: BeautifulSoup(f'<main>{html}</main>', 'html.parser')), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {e['name']: e for e in stored}


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
    return {e['name']: e for e in stored}


def blocks(*lines):
    return ''.join(f'<p>{line}</p>' for line in lines)


class FowlerTest(unittest.TestCase):
    PAGE = blocks('Uhengaparaoa, Taonga Tuku Iho', 'October 11, 2026 – May 16, 2027',
                  'Field Notes from Begumpura', 'by Rahee Punyashloka', 'August 9, 2026 – Summer 2027',
                  'Intersections: World Arts, Local Lives', 'Ongoing')

    def test_a_season_end_leaves_the_end_open_and_a_byline_is_not_the_title(self):
        events = run(fowler, 'scrape_fowler_museum_at_ucla', self.PAGE)
        self.assertEqual(sorted(events), ['Field Notes from Begumpura', 'Uhengaparaoa, Taonga Tuku Iho'])
        notes = events['Field Notes from Begumpura']
        self.assertEqual((notes['dates']['start'], notes['dates']['end']), (dt.date(2026, 8, 9), None))
        self.assertIn('free', notes['tags'])

    def test_a_full_range_is_read_as_dates(self):
        show = run(fowler, 'scrape_fowler_museum_at_ucla', self.PAGE)['Uhengaparaoa, Taonga Tuku Iho']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (dt.date(2026, 10, 11), dt.date(2027, 5, 16)))


class WendeTest(unittest.TestCase):
    def test_month_ranges_run_to_the_end_of_the_last_month(self):
        self.assertEqual(wende._month_range('Nov 2026-Jan 2027'), (dt.date(2026, 11, 1), dt.date(2027, 1, 31)))
        self.assertEqual(wende._month_range('Sep 2026–Feb 2028'), (dt.date(2026, 9, 1), dt.date(2028, 2, 29)))
        self.assertEqual(wende._month_range('Some title'), (None, None))

    @staticmethod
    def card(date, title, href, picture='https://wendemuseum.org/wp-content/smush-webp/2026/11/show.png.webp'):
        # The slider card as the site prints it: image, then a type label, the run and the title
        return (f'<div class="hero-slider__item swiper-slide"><a href="{href}"><img class="lazyload" data-src="{picture}" '
                f'src="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="></a><div class="hero-slider__text">'
                f'<div class="tp">Exhibition</div><div class="more-date">{date}</div><div class="title">{title}</div>'
                f'<a class="more-link" href="{href}"><span>See More</span></a></div></div>')

    def test_titles_notices_pictures_pages_and_the_free_tag(self):
        page = (self.card('Sep 2026-Jan 2027', 'Between Two Empires: Argentina in the Cold War', 'https://wendemuseum.org/exhibition/two/')
                + self.card('Nov 2026-Jan 2027', 'Bumdog Torres | THIS STRUCTURE WILL BE REMOVED WITHIN THE NEXT 48 HOURS',
                            '/exhibition/bumdog/'))
        events = run(wende, 'scrape_wende_museum', page)
        # the "Exhibition" label above each date is not a title
        self.assertEqual(sorted(events), ['Between Two Empires: Argentina in the Cold War', 'Bumdog Torres'])
        self.assertTrue(all('free' in e['tags'] for e in events.values()))
        bumdog = events['Bumdog Torres']['links']
        self.assertEqual(bumdog[0], {'link': 'https://wendemuseum.org/exhibition/bumdog/', 'description': 'Event Page'})
        self.assertEqual(bumdog[1], {'link': 'https://wendemuseum.org/wp-content/smush-webp/2026/11/show.png.webp',
                                     'description': 'Image'})

    def test_a_placeholder_picture_is_not_used_and_a_duplicate_card_is_stored_once(self):
        card = self.card('Nov 2026-Oct 2027', 'Competing Cosmologies', '/exhibition/cosmos/', picture='data:image/gif;base64,R0lG')
        events = run(wende, 'scrape_wende_museum', card + card)
        self.assertEqual(list(events), ['Competing Cosmologies'])
        self.assertEqual([l['description'] for l in events['Competing Cosmologies']['links']], ['Event Page'])


class SkirballTest(unittest.TestCase):
    def test_on_view_through_gives_an_end_date_only_and_ongoing_is_skipped(self):
        page = blocks('On View Now', 'Common Ground', 'On view through January 2, 2028',
                      'Visions and Values', 'Ongoing')
        show = run(skirball, 'scrape_skirball_cultural_center', page)['Common Ground']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (None, dt.date(2028, 1, 2)))
        self.assertNotIn('free', show['tags'])


class VincentPriceTest(unittest.TestCase):
    def test_the_archive_after_the_current_section_is_not_read(self):
        page = blocks('Exhibitions', 'Past Exhibitions',            # the menu link above the list
                      'CURRENT', 'The Buddhist Bug', 'September 26, 2026 – May 22, 2027',
                      'UPCOMING EXHIBITIONS', 'Almendárez', 'November 21, 2026 – May 22, 2027',
                      'PAST EXHIBITIONS', 'Old Show With A Live Looking Date', 'October 1, 2026 – December 31, 2026')
        self.assertEqual(sorted(run(vpam, 'scrape_vincent_price_art_museum', page)), ['Almendárez', 'The Buddhist Bug'])


class EighteenthStreetTest(unittest.TestCase):
    def test_ranges_are_exhibitions_and_an_evening_is_an_event(self):
        page = blocks('ON VIEW', 'Momo Nagano: Archeology of Motherhood', 'June 1, 2026', '-', 'June 1, 2027',
                      'UPCOMING EXHIBITIONS', 'Sage Ni’Ja Whitson: Revival', 'November 8, 2026 @ 2:00 pm', '-', '5:00 pm')
        events = run(eighteenth, 'scrape_eighteenth_street_arts_center', page)
        self.assertIn('exhibition', events['Momo Nagano: Archeology of Motherhood']['tags'])
        evening = events['Sage Ni’Ja Whitson: Revival']
        self.assertIn('event', evening['tags'])
        self.assertEqual(evening['dates'], {'start': dt.date(2026, 11, 8), 'end': dt.date(2026, 11, 8)})


class JanmTest(unittest.TestCase):
    def test_only_upcoming_and_special_entries_with_dates_are_read(self):
        page = blocks('Upcoming Exhibition', 'Jan 23 - Aug 29, 2027', 'Pictures of Belonging',
                      'Upcoming Exhibition', 'Ongoing', 'In the Future We Call Now',
                      'Traveling Display', 'Jul 15 - Dec 25, 2026', 'A Show Elsewhere')
        events = run(janm, 'scrape_japanese_american_national_museum', page)
        self.assertEqual(list(events), ['Pictures of Belonging'])
        self.assertEqual(events['Pictures of Belonging']['phase'], 'future')


class IcaLaTest(unittest.TestCase):
    PAGE = blocks('Current Exhibitions', 'Carl Cheng: Nature Never Loses', 'On view through February 28, 2027',
                  'Outdoor Projects', 'Zoe Walsh: Gathering', 'On view through February 28, 2027',
                  'Upcoming', 'Opening March 27, 2027', 'Teresa Baker: Somewhere Between', 'Opening November 07',
                  'Sming Sming Books', 'Find us on', 'Opening December 1', 'Not A Show')

    def test_current_shows_have_only_an_end_and_upcoming_ones_only_a_start(self):
        events = run(ica_la, 'scrape_ica_la', self.PAGE)
        self.assertEqual(sorted(events), ['Carl Cheng: Nature Never Loses', 'Sming Sming Books',
                                          'Teresa Baker: Somewhere Between', 'Zoe Walsh: Gathering'])
        self.assertEqual(events['Carl Cheng: Nature Never Loses']['dates'], {'start': None, 'end': dt.date(2027, 2, 28)})
        # No year given: the coming November 7
        self.assertEqual(events['Sming Sming Books']['dates']['start'], dt.date(2026, 11, 7))
        self.assertEqual(events['Teresa Baker: Somewhere Between']['phase'], 'future')


class MolaaTest(unittest.TestCase):
    PAGES = {
        'https://molaa.org/exhibitions/': '<a class="image-slide-anchor" href="/2026-red">x</a>'
                                          '<a class="image-slide-anchor" href="/2026-romero">x</a>'
                                          '<a class="image-slide-anchor" href="/molaa-collection-lab">x</a>'
                                          '<a class="image-slide-anchor">x</a>'
                                          '<a class="image-slide-anchor" href="/2025-old">x</a>',
        'https://molaa.org/2026-red': blocks('Donate', 'RED RED RED, Geometry of a Scar', 'ORGANIZED BY MIA ART COLLECTION',
                                             'Starting October 4, 2026 - February 21, 2027'),
        'https://molaa.org/2026-romero': blocks('Donate', 'Antonio Romero:', 'TROPICALIA [VOL2]', 'Exhibition Brochure',
                                                'Starting March 29, 2026'),
    }

    def test_current_slides_are_read_until_the_gap_and_titles_are_joined(self):
        events = run_pages(molaa, 'scrape_molaa', self.PAGES)
        self.assertEqual(sorted(events), ['Antonio Romero: TROPICALIA [VOL2]', 'RED RED RED, Geometry of a Scar'])
        self.assertEqual(events['RED RED RED, Geometry of a Scar']['dates'],
                         {'start': dt.date(2026, 10, 4), 'end': dt.date(2027, 2, 21)})
        self.assertIsNone(events['Antonio Romero: TROPICALIA [VOL2]']['dates']['end'])


class CaamTest(unittest.TestCase):
    @staticmethod
    def item(title, start, end, display='', text=None, teaser=None, main_image=None, image=None, slug='x'):
        content = {'start_date': start[0], 'start_year': start[1], 'end_date': end[0], 'end_year': end[1], 'display_date': display}
        if text is not None:
            content['text'] = text
        if teaser is not None:
            content['teaser'] = teaser
        if main_image:
            content['main_image'] = main_image
        item = {'title': title, 'contentUrl': f'https://caamuseum.org/content/3-exhibitions/{slug}',
                'url': f'https://caamuseum.org/exhibitions/2026/{slug}', 'content': content}
        if image:
            item['image'] = image
        return item

    @staticmethod
    def scrape(feed):
        stored = []
        response = mock.Mock(json=lambda: feed, raise_for_status=lambda: None)
        with mock.patch.object(caam.requests, 'get', return_value=response), \
                mock.patch.object(caam, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
            caam.scrape_california_african_american_museum(env='prod')
        return {e['name']: e for e in stored}

    def test_the_event_page_is_the_public_address_not_the_internal_content_path_which_is_a_403(self):
        events = self.scrape({'current': [self.item('Sadie Barnette: How to Fly', ('September 30', 2025), ('October 3', 2027), slug='sadie-barnette-how-to-fly')]})
        links = [l['link'] for l in events['Sadie Barnette: How to Fly']['links'] if l['description'] == 'Event Page']
        self.assertEqual(links, ['https://caamuseum.org/exhibitions/2026/sadie-barnette-how-to-fly'])

    def test_the_picture_files_are_still_found_under_the_content_path(self):
        events = self.scrape({'current': [self.item('Sinners', ('October 20', 2026), ('March 14', 2027), main_image='lead.jpg', slug='sinners')]})
        pictures = [l['link'] for l in events['Sinners']['links'] if l['description'] == 'Image']
        self.assertEqual(len(pictures), 1)
        # (the picture goes through the small-copy service, so the address is URL-encoded inside its link)
        self.assertIn('caamuseum.org/content/3-exhibitions/sinners/lead.jpg', urllib.parse.unquote(pictures[0]))

    def test_the_description_is_the_shows_own_text_from_the_feed(self):
        text = ('*How to Fly* is a site-specific photomural by visual artist Sadie Barnette installed in CAAM\u2019s atrium. '
                'Born and raised in Oakland, California, Barnette incorporates photographs she has taken of places.\n\n'
                '**Presented at Art + Practice**')
        events = self.scrape({'current': [
            self.item('Sadie Barnette: How to Fly', ('September 30', 2025), ('October 3', 2027), text=text),
            self.item('Teaser Only', ('October 1', 2026), ('March 1', 2027),
                      teaser='A new installation that explores memory, migration and the archive through film and sound.'),
            self.item('No Text', ('October 2', 2026), ('March 2', 2027))]})
        described = events['Sadie Barnette: How to Fly']['description']
        self.assertTrue(described.startswith('How to Fly is a site-specific photomural by visual artist Sadie Barnette'))
        self.assertNotIn('*', described)
        self.assertNotIn('Art + Practice', described)
        self.assertTrue(events['Teaser Only']['description'].startswith('A new installation that explores memory'))
        self.assertIsNone(events['No Text']['description'])

    def test_ongoing_and_offsite_entries_are_skipped(self):
        feed = {'current': [self.item('Sinners', ('October 20', 2026), ('March 14', 2027)),
                            self.item('Public Sculpture', ('June 21', 2023), ('June 21', 2030), 'Ongoing'),
                            self.item('Elsewhere', ('October 20', 2026), ('February 27', 2027),
                                      'October 20, 2026 - February 27, 2027 at Art + Practice')],
                'upcoming': [self.item('Fred Wilson', ('November 17', 2026), ('April 4', 2027))]}
        stored = []
        response = mock.Mock(json=lambda: feed, raise_for_status=lambda: None)
        with mock.patch.object(caam.requests, 'get', return_value=response), \
                mock.patch.object(caam, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
            caam.scrape_california_african_american_museum(env='prod')
        events = {e['name']: e for e in stored}
        self.assertEqual(sorted(events), ['Fred Wilson', 'Sinners'])
        self.assertEqual(events['Fred Wilson']['phase'], 'future')


class GalleryHelpersTest(unittest.TestCase):
    def test_date_label_reads_only_short_date_lines(self):
        self.assertEqual(_gallery.date_label('November 7 – December 19, 2026', TODAY), (dt.date(2026, 11, 7), dt.date(2026, 12, 19)))
        self.assertEqual(_gallery.date_label('On view though December 19', TODAY), (None, dt.date(2026, 12, 19)))
        self.assertIsNone(_gallery.date_label('November was a busy month for the gallery and its artists, who showed widely', TODAY))
        self.assertIsNone(_gallery.date_label('Los Angeles', TODAY))

    def test_a_run_already_over_is_moved_a_year_on(self):
        self.assertEqual(_gallery.next_year_if_past(dt.date(2025, 11, 21), dt.date(2026, 1, 30), TODAY),
                         (dt.date(2026, 11, 21), dt.date(2027, 1, 30)))
        self.assertEqual(_gallery.next_year_if_past(dt.date(2026, 11, 7), dt.date(2026, 12, 19), TODAY),
                         (dt.date(2026, 11, 7), dt.date(2026, 12, 19)))


class GalleryScrapersTest(unittest.TestCase):
    def test_night_gallery_capitals_and_year(self):
        page = blocks('Upcoming', 'Past', 'TIDAWHITNEY LEK', 'Something Familiar', 'NOVEMBER 21 - JANUARY 30, 2026')
        events = run(night_gallery, 'scrape_night_gallery', page)
        show = events['Tidawhitney Lek: Something Familiar']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 21), 'end': dt.date(2027, 1, 30)})

    def test_kordansky_keeps_only_los_angeles(self):
        page = blocks('Current', 'Upcoming', 'Past', 'Jenna Gribbon', 'Projections', 'November 6 – December 19, 2026', 'New York',
                      'Chris Martin', 'In Memory of My Feelings', 'November 13 – December 16, 2026', 'Los Angeles',
                      'Abraham Lincoln Walker: After World, 1980–1991', 'November 13 – December 16, 2026', 'Los Angeles')
        events = run(kordansky, 'scrape_david_kordansky_gallery', page)
        self.assertEqual(sorted(events), ['Abraham Lincoln Walker: After World, 1980–1991', 'Chris Martin: In Memory of My Feelings'])

    def test_charlie_james_solo_and_curated_names_and_repeats(self):
        page = blocks('EXHIBITIONS', 'Featured', 'Eat Happy', 'Narsiso Martinez', 'Eat Happy', 'September 25 - November 7, 2026', 'Read more →',
                      'Food and Beyond, Beyond Food', 'Food and Beyond, Beyond Food', 'Curated by Narsiso Martinez',
                      'September 25 - November 7, 2026', 'Read more →', 'UPCOMING', 'Vecinos', 'Rigoberto Torres', 'Vecinos',
                      'November 6 - December 19, 2026', 'Read more →', 'Vecinos', 'Rigoberto Torres', 'Vecinos',
                      'November 6 - December 19, 2026', 'Read more →')
        events = run(charlie_james, 'scrape_charlie_james_gallery', page)
        self.assertEqual(sorted(events), ['Food and Beyond, Beyond Food', 'Narsiso Martinez: Eat Happy', 'Rigoberto Torres: Vecinos'])

    def test_gagosian_keeps_beverly_hills_and_reads_a_short_run(self):
        page = blocks('Exhibitions', 'List', 'Brice Marden', 'I Am Plane Image', 'September 15', '–', 'December 12, 2026', 'West 21st Street, New York',
                      'Friends and Legends', 'The Collection of Michael Chow', 'November 4', '–', '7, 2026', 'Beverly Hills')
        events = run(gagosian, 'scrape_gagosian_beverly_hills', page)
        self.assertEqual(list(events), ['Friends and Legends: The Collection of Michael Chow'])
        self.assertEqual(events['Friends and Legends: The Collection of Michael Chow']['dates'],
                         {'start': dt.date(2026, 11, 4), 'end': dt.date(2026, 11, 7)})

    def test_anat_ebgi_keeps_los_angeles_in_the_current_section(self):
        page = blocks('Current & Announced Exhibitions', 'Erin Wright: Memnosphere', 'September 19, 2026', '—', 'January 16, 2027', ',',
                      '6150 Wilshire Blvd, Suite 5, Los Angeles, CA 90048, USA', 'Wilshire',
                      'Meeson Pae: Seed Memory', 'November 6', '—', 'December 19, 2026', ',',
                      '372 Broadway, New York City, NY 10013, USA', 'Tribeca', 'Past Exhibitions',
                      'Jordan Nassar: Describing Clouds', 'September 19', '—', 'October 31, 2026', ',',
                      '6150 Wilshire Blvd, Suite 5, Los Angeles, CA 90048, USA', 'Wilshire')
        events = run(anat_ebgi, 'scrape_anat_ebgi_gallery', page)
        self.assertEqual(list(events), ['Erin Wright: Memnosphere'])

    def test_commonwealth_and_council_skips_fair_booths(self):
        page = blocks('Visit', 'Now', '2026', 'FOLDING BOY AND BLUE', 'Michelle Lopez', 'November 7, 2026', '–', 'December 19, 2026',
                      'Art Basel', 'American Artist', 'November 1, 2026', '–', 'November 8, 2026')
        events = run(commonwealth, 'scrape_commonwealth_and_council', page)
        self.assertEqual(list(events), ['Michelle Lopez: FOLDING BOY AND BLUE'])


if __name__ == '__main__':
    unittest.main()
